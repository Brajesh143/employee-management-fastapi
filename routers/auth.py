from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from crud.auth import login_employee, change_password
from auth.dependencies import get_current_active_user
from models.employee import Employee
from schemas.auth import (
    LoginRequest,
    Token,
    ChangePassword,
)

router = APIRouter()


# ==============================
# Login
# ==============================

@router.post(
    "/login",
    response_model=Token,
    summary="Employee Login"
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate employee and return JWT token.
    """

    return login_employee(
        db=db,
        login_data=login_data
    )


# ==============================
# Current Logged In User
# ==============================

@router.get(
    "/me",
    summary="Get Current Employee"
)
def get_current_employee(
    current_user: Employee = Depends(
        get_current_active_user
    )
):
    """
    Return currently authenticated employee.
    """

    return current_user


# ==============================
# Change Password
# ==============================

@router.put(
    "/change-password",
    summary="Change Password"
)
def update_password(
    password_data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        get_current_active_user
    )
):
    """
    Change current employee password.
    """

    return change_password(
        db=db,
        employee=current_user,
        password_data=password_data
    )