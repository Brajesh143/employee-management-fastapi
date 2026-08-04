from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from database import get_db
from models.employee import Employee
from auth.jwt import JWTHandler

# This tells FastAPI where the login endpoint is
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Employee:
    """
    Returns the currently authenticated employee.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    try:
        payload = JWTHandler.verify_access_token(token)

        if payload is None:
            raise credentials_exception

        employee_id = payload.get("sub")

        if employee_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    employee = (
        db.query(Employee)
        .filter(Employee.id == int(employee_id))
        .first()
    )

    if employee is None:
        raise credentials_exception

    return employee


def get_current_active_user(
    current_user: Employee = Depends(get_current_user)
) -> Employee:
    """
    Returns only active employees.
    """

    if not current_user.is_active:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive employee"
        )

    return current_user