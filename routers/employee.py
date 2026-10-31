from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth.permissions import (
    can_access_employee,
    ensure_role_assignment_allowed,
    has_permission,
    require_permission,
)
from models.employee import Employee
from schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from schemas.employee_csv import EmployeeImportPreview
from schemas.employee_document import EmployeeDocumentResponse
from schemas.employee_exit import EmployeeExitRequest
from database import get_db
from crud import employee as crud
from auth.dependencies import get_current_user
from services.employee_csv import (
    MAX_IMPORT_SIZE,
    export_employees_csv,
    preview_employee_csv,
)
from services.employee_documents import (
    MAX_DOCUMENT_SIZE,
    create_employee_document,
    get_employee_document,
    get_employee_documents,
)
from services.employee_document_storage import get_document_storage

router = APIRouter()


def _scope_to_reporting_team(
    db: Session,
    current_user: Employee,
    reporting_manager_id: int | None,
) -> int | None:
    if not has_permission(db, current_user, "employee:team:read"):
        return reporting_manager_id
    if reporting_manager_id not in (None, current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Managers may only view their own reporting team.",
        )
    return current_user.id


@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("employee:create"))
    ]
)
def create_employee_api(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    ensure_role_assignment_allowed(db, current_user, employee.role_id)

    try:
        return crud.create_employee(db, employee)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

@router.get(
    "/",
    response_model=list[EmployeeResponse],
    dependencies=[Depends(require_permission("employee:read"))]
)
def get_employees(
    response: Response,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    q: str | None = Query(default=None, max_length=100),
    department_id: int | None = Query(default=None, ge=1),
    designation_id: int | None = Query(default=None, ge=1),
    role_id: int | None = Query(default=None, ge=1),
    reporting_manager_id: int | None = Query(default=None, ge=1),
    is_active: bool | None = None,
    employee_status: str | None = Query(default=None, alias="status", max_length=20),
    joining_date_from: date | None = None,
    joining_date_to: date | None = None,
    sort_by: str = Query(default="employee_code"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
):
    reporting_manager_id = _scope_to_reporting_team(
        db,
        current_user,
        reporting_manager_id,
    )
    if sort_by not in crud.EMPLOYEE_SORT_COLUMNS:
        allowed = ", ".join(sorted(crud.EMPLOYEE_SORT_COLUMNS))
        raise HTTPException(
            status_code=422,
            detail=f"sort_by must be one of: {allowed}",
        )
    if (
        joining_date_from is not None
        and joining_date_to is not None
        and joining_date_from > joining_date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="joining_date_from must be on or before joining_date_to.",
        )

    employees, total = crud.get_employees(
        db,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        q=q,
        department_id=department_id,
        designation_id=designation_id,
        role_id=role_id,
        reporting_manager_id=reporting_manager_id,
        is_active=is_active,
        status=employee_status,
        joining_date_from=joining_date_from,
        joining_date_to=joining_date_to,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    return employees


@router.get(
    "/export",
    dependencies=[Depends(require_permission("employee:export"))],
)
def export_employees(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, max_length=100),
    department_id: int | None = Query(default=None, ge=1),
    designation_id: int | None = Query(default=None, ge=1),
    role_id: int | None = Query(default=None, ge=1),
    reporting_manager_id: int | None = Query(default=None, ge=1),
    is_active: bool | None = None,
    employee_status: str | None = Query(default=None, alias="status", max_length=20),
    joining_date_from: date | None = None,
    joining_date_to: date | None = None,
):
    if (
        joining_date_from is not None
        and joining_date_to is not None
        and joining_date_from > joining_date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="joining_date_from must be on or before joining_date_to.",
        )
    employees = crud.get_employees_for_export(
        db,
        q=q,
        department_id=department_id,
        designation_id=designation_id,
        role_id=role_id,
        reporting_manager_id=reporting_manager_id,
        is_active=is_active,
        status=employee_status,
        joining_date_from=joining_date_from,
        joining_date_to=joining_date_to,
    )
    return StreamingResponse(
        iter([export_employees_csv(employees)]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="employees.csv"',
            "X-Total-Count": str(len(employees)),
        },
    )


@router.post(
    "/import/preview",
    response_model=EmployeeImportPreview,
    dependencies=[Depends(require_permission("employee:import"))],
)
async def preview_employee_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.filename is None or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    content = await file.read(MAX_IMPORT_SIZE + 1)
    try:
        return preview_employee_csv(db, content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()


@router.post(
    "/{employee_id}/documents",
    response_model=EmployeeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("document:manage"))],
)
async def upload_employee_document(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    employee = crud.get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    content = await file.read(MAX_DOCUMENT_SIZE + 1)
    try:
        return create_employee_document(
            db,
            employee,
            file.filename or "",
            content,
            get_document_storage(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()


@router.get(
    "/{employee_id}/documents",
    response_model=list[EmployeeDocumentResponse],
    dependencies=[Depends(require_permission("document:manage"))],
)
def list_employee_documents(employee_id: int, db: Session = Depends(get_db)):
    if crud.get_employee(db, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return get_employee_documents(db, employee_id)


@router.get(
    "/documents/{document_id}/download",
    dependencies=[Depends(require_permission("document:manage"))],
)
def download_employee_document(document_id: int, db: Session = Depends(get_db)):
    document = get_employee_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        stream = get_document_storage().open(document.storage_key)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Document file not found") from error

    def content_chunks():
        with stream:
            while chunk := stream.read(64 * 1024):
                yield chunk

    encoded_name = quote(document.file_name, safe="")
    return StreamingResponse(
        content_chunks(),
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{encoded_name}"
            ),
            "Content-Length": str(document.file_size),
        },
    )


@router.post(
    "/{employee_id}/exit",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:update"))],
)
def exit_employee(
    employee_id: int,
    exit_request: EmployeeExitRequest,
    db: Session = Depends(get_db),
):
    try:
        employee = crud.exit_employee(
            db,
            employee_id,
            exit_request.exit_date,
            exit_request.exit_reason,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:read"))]
)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    employee = crud.get_employee(
        db,
        employee_id
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    if not can_access_employee(db, current_user, employee.id):
        raise HTTPException(status_code=404, detail="Employee not found")

    return employee

@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:update"))]
)
def update_employee(
    employee_id: int,
    employee: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    if "role_id" in employee.model_fields_set:
        ensure_role_assignment_allowed(db, current_user, employee.role_id)

    try:
        updated_employee = crud.update_employee(employee_id, employee, db)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if not updated_employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    return updated_employee

@router.delete(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:delete"))]
)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    deleted_employee = crud.delete_employee(
        db,
        employee_id
    )

    if not deleted_employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    return deleted_employee
