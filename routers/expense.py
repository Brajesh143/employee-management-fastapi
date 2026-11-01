from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import has_permission, require_any_permission, require_permission
from database import get_db
from models.employee import Employee
from models.expense_claim import ExpenseClaim
from schemas.expense import ExpenseClaimCreate, ExpenseClaimResponse, ExpenseReview
from services.employee_document_storage import get_document_storage
from services.expenses import (
    MAX_RECEIPT_SIZE,
    create_expense_claim,
    expense_scope_query,
    reimburse_expense,
    review_expense,
    save_receipt,
)

router = APIRouter()


@router.post(
    "/",
    response_model=ExpenseClaimResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_claim(
    payload: ExpenseClaimCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("expense:create")),
):
    return create_expense_claim(
        db,
        payload,
        employee_id=current_user.id,
        actor_id=current_user.id,
    )


@router.get(
    "/",
    response_model=list[ExpenseClaimResponse],
    dependencies=[
        Depends(
            require_any_permission(
                "expense:read",
                "expense:approve",
                "reimbursement:read",
                "reimbursement:approve",
            )
        )
    ],
)
def list_claims(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission(
            "expense:read",
            "expense:approve",
            "reimbursement:read",
            "reimbursement:approve",
        )
    ),
):
    return expense_scope_query(db, current_user).order_by(
        ExpenseClaim.created_at.desc(),
        ExpenseClaim.id.desc(),
    ).all()


@router.post(
    "/{claim_id}/receipt",
    response_model=ExpenseClaimResponse,
)
async def upload_receipt(
    claim_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("expense:create")),
):
    claim = (
        db.query(ExpenseClaim)
        .filter(
            ExpenseClaim.id == claim_id,
            ExpenseClaim.employee_id == current_user.id,
        )
        .first()
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Expense claim not found.")
    content = await file.read(MAX_RECEIPT_SIZE + 1)
    try:
        return save_receipt(
            db,
            claim,
            file.filename or "",
            content,
            get_document_storage(),
            actor_id=current_user.id,
        )
    finally:
        await file.close()


@router.get(
    "/{claim_id}/receipt",
    dependencies=[
        Depends(
            require_any_permission(
                "expense:read",
                "expense:approve",
                "reimbursement:read",
                "reimbursement:approve",
            )
        )
    ],
)
def download_receipt(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission(
            "expense:read",
            "expense:approve",
            "reimbursement:read",
            "reimbursement:approve",
        )
    ),
):
    claim = expense_scope_query(db, current_user).filter(
        ExpenseClaim.id == claim_id
    ).first()
    if claim is None or claim.receipt_storage_key is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    try:
        stream = get_document_storage().open(claim.receipt_storage_key)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Receipt file not found.") from error
    encoded_name = quote(claim.receipt_name or "receipt", safe="")
    return StreamingResponse(
        stream,
        media_type=claim.receipt_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "Content-Length": str(claim.receipt_size or 0),
        },
    )


@router.post(
    "/{claim_id}/approve",
    response_model=ExpenseClaimResponse,
    dependencies=[Depends(require_permission("expense:approve"))],
)
def approve_claim(
    claim_id: int,
    payload: ExpenseReview,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("expense:approve")),
):
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id).first()
    if claim is None or claim.employee_id == current_user.id:
        raise HTTPException(status_code=404, detail="Expense claim not found.")
    if not _can_review_claim(db, current_user, claim):
        raise HTTPException(status_code=404, detail="Expense claim not found.")
    return review_expense(
        db,
        claim,
        reviewer=current_user,
        approve=True,
        comment=payload.comment,
    )


@router.post(
    "/{claim_id}/reject",
    response_model=ExpenseClaimResponse,
    dependencies=[Depends(require_permission("expense:approve"))],
)
def reject_claim(
    claim_id: int,
    payload: ExpenseReview,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("expense:approve")),
):
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id).first()
    if claim is None or claim.employee_id == current_user.id:
        raise HTTPException(status_code=404, detail="Expense claim not found.")
    if not _can_review_claim(db, current_user, claim):
        raise HTTPException(status_code=404, detail="Expense claim not found.")
    return review_expense(
        db,
        claim,
        reviewer=current_user,
        approve=False,
        comment=payload.comment,
    )


@router.post(
    "/{claim_id}/reimburse",
    response_model=ExpenseClaimResponse,
    dependencies=[Depends(require_permission("reimbursement:approve"))],
)
def reimburse_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_permission("reimbursement:approve")
    ),
):
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Expense claim not found.")
    return reimburse_expense(
        db,
        claim,
        actor_id=current_user.id,
    )


def _can_review_claim(
    db: Session,
    reviewer: Employee,
    claim: ExpenseClaim,
) -> bool:
    if has_permission(db, reviewer, "employee:read:all"):
        return True
    if not has_permission(db, reviewer, "employee:team:read"):
        return has_permission(db, reviewer, "expense:approve")
    return (
        db.query(Employee.id)
        .filter(
            Employee.id == claim.employee_id,
            Employee.reporting_manager_id == reviewer.id,
        )
        .first()
        is not None
    )
