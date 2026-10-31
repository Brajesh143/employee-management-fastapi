from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.department import Department  # noqa: F401
from models.designation import Designation
from models.employee import Employee
from models.employee_document import EmployeeDocument  # noqa: F401
from models.leave import Leave  # noqa: F401
from models.role import Role  # noqa: F401
from models.shift import Shift  # noqa: F401
from schemas.employee import EmployeeCreate, EmployeeUpdate
from auth.hashing import Hash
from services.employee_document_storage import get_document_storage


def _validate_assignment(
    db: Session,
    employee_id: int | None,
    reporting_manager_id: int | None,
    designation_id: int | None,
) -> None:
    if reporting_manager_id is not None:
        if reporting_manager_id == employee_id:
            raise ValueError("An employee cannot report to themselves.")

        manager = (
            db.query(Employee)
            .filter(Employee.id == reporting_manager_id)
            .first()
        )
        if manager is None or not manager.is_active:
            raise ValueError("Reporting manager must be an active employee.")

        checked_manager_ids: set[int] = set()
        while manager is not None:
            if manager.id == employee_id:
                raise ValueError("Reporting manager assignment would create a cycle.")
            if manager.id in checked_manager_ids:
                raise ValueError("Reporting manager hierarchy already contains a cycle.")
            checked_manager_ids.add(manager.id)
            manager = (
                db.query(Employee)
                .filter(Employee.id == manager.reporting_manager_id)
                .first()
                if manager.reporting_manager_id is not None
                else None
            )

    if designation_id is not None:
        designation = (
            db.query(Designation)
            .filter(
                Designation.id == designation_id,
                Designation.is_active.is_(True),
            )
            .first()
        )
        if designation is None:
            raise ValueError("Designation must exist and be active.")


def create_employee(db: Session, employee: EmployeeCreate):
    _validate_assignment(
        db,
        employee_id=None,
        reporting_manager_id=employee.reporting_manager_id,
        designation_id=employee.designation_id,
    )
    db_employee = Employee(
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        phone=employee.phone,
        gender=employee.gender,
        dob=employee.dob,
        joining_date=employee.joining_date,
        department_id=employee.department_id,
        designation_id=employee.designation_id,
        role_id=employee.role_id,
        reporting_manager_id=employee.reporting_manager_id,
        shift_id=employee.shift_id,
        address=employee.address,
        salary=employee.salary,
        profile_image=employee.profile_image,
        status=employee.status,
        password_hash=Hash.hash_password(employee.password),
    )

    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    return db_employee


EMPLOYEE_SORT_COLUMNS = {
    "employee_code": Employee.employee_code,
    "first_name": Employee.first_name,
    "last_name": Employee.last_name,
    "email": Employee.email,
    "joining_date": Employee.joining_date,
    "status": Employee.status,
    "is_active": Employee.is_active,
    "department_id": Employee.department_id,
    "designation_id": Employee.designation_id,
    "reporting_manager_id": Employee.reporting_manager_id,
    "created_at": Employee.created_at,
}


def employee_query(
    db: Session,
    *,
    q: str | None = None,
    department_id: int | None = None,
    designation_id: int | None = None,
    role_id: int | None = None,
    reporting_manager_id: int | None = None,
    is_active: bool | None = None,
    status: str | None = None,
    joining_date_from: date | None = None,
    joining_date_to: date | None = None,
):
    query = db.query(Employee)

    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Employee.employee_code.ilike(search),
                Employee.first_name.ilike(search),
                Employee.last_name.ilike(search),
                Employee.email.ilike(search),
            )
        )
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)
    if designation_id is not None:
        query = query.filter(Employee.designation_id == designation_id)
    if role_id is not None:
        query = query.filter(Employee.role_id == role_id)
    if reporting_manager_id is not None:
        query = query.filter(Employee.reporting_manager_id == reporting_manager_id)
    if is_active is not None:
        query = query.filter(Employee.is_active.is_(is_active))
    if status:
        query = query.filter(Employee.status == status)
    if joining_date_from is not None:
        query = query.filter(Employee.joining_date >= joining_date_from)
    if joining_date_to is not None:
        query = query.filter(Employee.joining_date <= joining_date_to)
    return query


def get_employees(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "employee_code",
    sort_order: str = "asc",
    q: str | None = None,
    department_id: int | None = None,
    designation_id: int | None = None,
    role_id: int | None = None,
    reporting_manager_id: int | None = None,
    is_active: bool | None = None,
    status: str | None = None,
    joining_date_from: date | None = None,
    joining_date_to: date | None = None,
) -> tuple[list[Employee], int]:
    query = employee_query(
        db,
        q=q,
        department_id=department_id,
        designation_id=designation_id,
        role_id=role_id,
        reporting_manager_id=reporting_manager_id,
        is_active=is_active,
        status=status,
        joining_date_from=joining_date_from,
        joining_date_to=joining_date_to,
    )
    total = query.count()
    sort_column = EMPLOYEE_SORT_COLUMNS[sort_by]
    sort_expression = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    employees = (
        query.order_by(sort_expression.nulls_last(), Employee.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return employees, total


def get_employees_for_export(
    db: Session,
    *,
    q: str | None = None,
    department_id: int | None = None,
    designation_id: int | None = None,
    role_id: int | None = None,
    reporting_manager_id: int | None = None,
    is_active: bool | None = None,
    status: str | None = None,
    joining_date_from: date | None = None,
    joining_date_to: date | None = None,
) -> list[Employee]:
    return (
        employee_query(
            db,
            q=q,
            department_id=department_id,
            designation_id=designation_id,
            role_id=role_id,
            reporting_manager_id=reporting_manager_id,
            is_active=is_active,
            status=status,
            joining_date_from=joining_date_from,
            joining_date_to=joining_date_to,
        )
        .order_by(Employee.employee_code.asc(), Employee.id.asc())
        .all()
    )

def get_employee(db: Session, employee_id: int):
    return (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .first()
    )

def update_employee(employee_id: int, employee: EmployeeUpdate, db: Session):
    db_employee = get_employee(db, employee_id)

    if not db_employee:
        return None

    update_data = employee.model_dump(exclude_unset=True)
    _validate_assignment(
        db,
        employee_id=employee_id,
        reporting_manager_id=update_data.get(
            "reporting_manager_id",
            db_employee.reporting_manager_id,
        ),
        designation_id=update_data.get("designation_id", db_employee.designation_id),
    )

    for key, value in update_data.items():
        setattr(db_employee, key, value)

    db.commit()
    db.refresh(db_employee)

    return db_employee


def exit_employee(
    db: Session,
    employee_id: int,
    exit_date: date,
    exit_reason: str,
):
    db_employee = get_employee(db, employee_id)

    if not db_employee:
        return None

    if db_employee.exit_date is not None:
        raise ValueError("Employee has already been exited.")

    db_employee.exit_date = exit_date
    db_employee.exit_reason = exit_reason
    db_employee.is_active = False
    db_employee.status = "Exited"
    db.commit()
    db.refresh(db_employee)

    return db_employee


def delete_employee(db: Session, employee_id: int):
    db_employee = get_employee(db, employee_id)

    if db_employee is None:
        return None

    storage_keys = [
        document.storage_key for document in db_employee.documents
    ]
    db.delete(db_employee)
    db.commit()
    storage = get_document_storage()
    for storage_key in storage_keys:
        storage.delete(storage_key)
    return db_employee
