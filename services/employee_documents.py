from pathlib import PurePath, PurePosixPath
from uuid import uuid4

from sqlalchemy.orm import Session

from models.employee import Employee
from models.employee_document import EmployeeDocument
from services.audit import write_audit_log
from services.employee_document_storage import DocumentStorage

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
}


def create_employee_document(
    db: Session,
    employee: Employee,
    file_name: str,
    content: bytes,
    storage: DocumentStorage,
    *,
    actor_id: int | None = None,
) -> EmployeeDocument:
    safe_name = PurePosixPath(file_name.replace("\\", "/")).name.strip()
    if not safe_name or len(safe_name) > 255:
        raise ValueError("Filename must be between 1 and 255 characters.")
    if not content:
        raise ValueError("Uploaded document is empty.")
    if len(content) > MAX_DOCUMENT_SIZE:
        raise ValueError("Document exceeds the 10 MB upload limit.")

    extension = PurePath(safe_name).suffix.lower()
    document_type = ALLOWED_DOCUMENT_TYPES.get(extension)
    if document_type is None or not document_type[1](content):
        raise ValueError("Only valid PDF, PNG, and JPEG documents are supported.")

    content_type = document_type[0]
    storage_key = f"employees/{employee.id}/{uuid4().hex}{extension}"
    storage.save(storage_key, content)

    document = EmployeeDocument(
        employee_id=employee.id,
        file_name=safe_name,
        storage_key=storage_key,
        content_type=content_type,
        file_size=len(content),
    )
    try:
        db.add(document)
        db.flush()
        write_audit_log(
            db,
            actor_id=actor_id,
            action="employee.document.upload",
            resource_type="employee_document",
            resource_id=document.id,
            after={
                "employee_id": employee.id,
                "file_name": document.file_name,
                "content_type": document.content_type,
                "file_size": document.file_size,
            },
        )
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise
    return document


def get_employee_documents(db: Session, employee_id: int) -> list[EmployeeDocument]:
    return (
        db.query(EmployeeDocument)
        .filter(EmployeeDocument.employee_id == employee_id)
        .order_by(EmployeeDocument.created_at.desc(), EmployeeDocument.id.desc())
        .all()
    )


def get_employee_document(db: Session, document_id: int) -> EmployeeDocument | None:
    return (
        db.query(EmployeeDocument)
        .filter(EmployeeDocument.id == document_id)
        .first()
    )
