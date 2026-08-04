from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.hashing import Hash
from auth.jwt import JWTHandler
from models.employee import Employee
from schemas.auth import LoginRequest, ChangePassword


def get_employee_by_email(
    db: Session,
    email: str
):
    """
    Get employee by email.
    """
    normalized_email = email.strip().lower()

    employee_data = (
        db.query(Employee)
        .filter(func.lower(Employee.email) == normalized_email)
        .first()
    )

    return employee_data


def authenticate_employee(
    db: Session,
    login_data: LoginRequest
) -> Employee | None:
    """
    Verify employee credentials.
    """
    print("Authenticating employee with email:", login_data.email)
    employee = get_employee_by_email(
        db,
        login_data.email
    )

    print("employee data after fetch", employee)

    if employee is None:
        return None

    if not employee.is_active:
        return None

    if not employee.password_hash:
        return None

    if not Hash.verify_password(
        login_data.password,
        employee.password_hash
    ):
        return None

    return employee


def login_employee(
    db: Session,
    login_data: LoginRequest
):
    """
    Authenticate employee and generate JWT.
    """

    print("Logging in employee with email:", login_data)
    employee = authenticate_employee(
        db,
        login_data
    )

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    role_name = getattr(employee.role, "name", None)

    access_token = JWTHandler.create_access_token(
        data={
            "sub": str(employee.id),
            "email": employee.email,
            "role": role_name
        }
    )

    employee.last_login = datetime.now(timezone.utc)

    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def change_password(
    db: Session,
    employee: Employee,
    password_data: ChangePassword
):
    """
    Change employee password.
    """

    if not Hash.verify_password(
        password_data.current_password,
        employee.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    if (
        password_data.new_password
        != password_data.confirm_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )

    employee.password_hash = Hash.hash_password(
        password_data.new_password
    )

    employee.password_changed_at = datetime.now(timezone.utc)

    db.commit()

    db.refresh(employee)

    return {
        "message": "Password changed successfully"
    }


def update_last_login(
    db: Session,
    employee: Employee
):
    """
    Update employee last login timestamp.
    """

    employee.last_login = datetime.now(timezone.utc)

    db.commit()


def deactivate_employee(
    db: Session,
    employee: Employee
):
    """
    Disable employee account.
    """

    employee.is_active = False

    db.commit()

    db.refresh(employee)

    return employee