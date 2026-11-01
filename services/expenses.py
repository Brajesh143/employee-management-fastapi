from datetime import datetime
from pathlib import PurePath, PurePosixPath
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from auth.permissions import has_permission
from models.employee import Employee
from models.expense_claim import ExpenseClaim
from schemas.expense import ExpenseClaimCreate
from services.audit import write_audit_log
from services.employee_document_storage import DocumentStorage

MAX_RECEIPT_SIZE = 10 * 1024 * 1024
ALLOWED_RECEIPTS = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
}


def expense_snapshot(claim: ExpenseClaim) -> dict[str, object]:
    return {
        "id": claim.id,
        "employee_id": claim.employee_id,
        "expense_date": claim.expense_date,
        "category": claim.category,
        "amount": claim.amount,
        "description": claim.description,
        "status": claim.status,
        "reimbursement_status": claim.reimbursement_status,
        "receipt_name": claim.receipt_name,
    }


def expense_scope_query(db: Session, user: Employee) -> Query:
    query = db.query(ExpenseClaim)
    if (
        has_permission(db, user, "employee:read:all")
        or has_permission(db, user, "reimbursement:approve")
        or (
            has_permission(db, user, "expense:approve")
            and not has_permission(db, user, "employee:team:read")
        )
    ):
        return query
    if has_permission(db, user, "employee:team:read"):
        employee_ids = db.query(Employee.id).filter(
            (Employee.id == user.id)
            | (Employee.reporting_manager_id == user.id)
        )
        return query.filter(ExpenseClaim.employee_id.in_(employee_ids))
    return query.filter(ExpenseClaim.employee_id == user.id)


def create_expense_claim(
    db: Session,
    payload: ExpenseClaimCreate,
    *,
    employee_id: int,
    actor_id: int,
) -> ExpenseClaim:
    claim = ExpenseClaim(
        employee_id=employee_id,
        expense_date=payload.expense_date,
        category=payload.category,
        amount=payload.amount,
        description=payload.description,
    )
    db.add(claim)
    db.flush()
    write_audit_log(
        db,
        actor_id=actor_id,
        action="expense.create",
        resource_type="expense_claim",
        resource_id=claim.id,
        after=expense_snapshot(claim),
    )
    db.commit()
    db.refresh(claim)
    return claim


def save_receipt(
    db: Session,
    claim: ExpenseClaim,
    file_name: str,
    content: bytes,
    storage: DocumentStorage,
    *,
    actor_id: int,
) -> ExpenseClaim:
    safe_name = PurePosixPath(file_name.replace("\\", "/")).name.strip()
    if not safe_name or len(safe_name) > 255:
        raise HTTPException(
            status_code=400,
            detail="Filename must be between 1 and 255 characters.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded receipt is empty.")
    if len(content) > MAX_RECEIPT_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Receipt exceeds the 10 MB upload limit.",
        )
    receipt_format = ALLOWED_RECEIPTS.get(PurePath(safe_name).suffix.lower())
    if receipt_format is None or not receipt_format[1](content):
        raise HTTPException(
            status_code=400,
            detail="Only valid PDF, PNG, and JPEG receipts are supported.",
        )
    if claim.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receipts can only be uploaded to pending claims.",
        )

    content_type = receipt_format[0]
    storage_key = f"expenses/{claim.id}/{uuid4().hex}{PurePath(safe_name).suffix.lower()}"
    storage.save(storage_key, content)
    old_storage_key = claim.receipt_storage_key
    before = expense_snapshot(claim)
    claim.receipt_name = safe_name
    claim.receipt_storage_key = storage_key
    claim.receipt_content_type = content_type
    claim.receipt_size = len(content)
    try:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="expense.receipt.upload",
            resource_type="expense_claim",
            resource_id=claim.id,
            before=before,
            after=expense_snapshot(claim),
        )
        db.commit()
        db.refresh(claim)
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise
    if old_storage_key:
        storage.delete(old_storage_key)
    return claim


def review_expense(
    db: Session,
    claim: ExpenseClaim,
    *,
    reviewer: Employee,
    approve: bool,
    comment: str | None,
) -> ExpenseClaim:
    if claim.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Expense claim is already {claim.status.lower()}.",
        )
    if approve and claim.receipt_storage_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload a valid receipt before approving this claim.",
        )
    before = expense_snapshot(claim)
    claim.status = "Approved" if approve else "Rejected"
    claim.reimbursement_status = "Pending" if approve else "Not eligible"
    claim.reviewed_by = reviewer.id
    claim.reviewed_at = datetime.utcnow()
    claim.review_comment = comment.strip() if comment else None
    write_audit_log(
        db,
        actor_id=reviewer.id,
        action=f"expense.{claim.status.lower()}",
        resource_type="expense_claim",
        resource_id=claim.id,
        before=before,
        after=expense_snapshot(claim),
    )
    db.commit()
    db.refresh(claim)
    return claim


def reimburse_expense(
    db: Session,
    claim: ExpenseClaim,
    *,
    actor_id: int,
) -> ExpenseClaim:
    if claim.status != "Approved" or claim.reimbursement_status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved, unpaid claims can be reimbursed.",
        )
    before = expense_snapshot(claim)
    claim.reimbursement_status = "Paid"
    claim.reimbursed_by = actor_id
    claim.reimbursed_at = datetime.utcnow()
    write_audit_log(
        db,
        actor_id=actor_id,
        action="expense.reimburse",
        resource_type="expense_claim",
        resource_id=claim.id,
        before=before,
        after=expense_snapshot(claim),
    )
    db.commit()
    db.refresh(claim)
    return claim
