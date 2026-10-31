from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database import get_db
from crud.auth import login_employee, change_password, revoke_access_token
from auth.dependencies import get_current_active_user, oauth2_scheme
from models.employee import Employee
from schemas.auth import (
    LoginRequest,
    Token,
    ChangePassword,
)
from schemas.employee import EmployeeResponse

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


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke the current access token",
)
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_active_user),
) -> Response:
    revoke_access_token(db, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==============================
# Current Logged In User
# ==============================

@router.get(
    "/me",
    response_model=EmployeeResponse,
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