from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    """
    Schema used when a user logs in.
    """

    email: str = Field(
        ...,
        description="Employee email address"
    )

    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Employee password"
    )


class Token(BaseModel):
    """
    JWT Token Response
    """

    access_token: str

    token_type: str = "bearer"


class TokenData(BaseModel):
    """
    Data extracted from JWT.
    """

    employee_id: Optional[int] = None

    email: Optional[str] = None

    role: Optional[str] = None


class ChangePassword(BaseModel):
    """
    Change Password Request
    """

    current_password: str = Field(
        ...,
        min_length=6
    )

    new_password: str = Field(
        ...,
        min_length=6
    )

    confirm_password: str = Field(
        ...,
        min_length=6
    )


class ForgotPassword(BaseModel):
    """
    Forgot Password Request
    """

    email: str


class ResetPassword(BaseModel):
    """
    Reset Password
    """

    token: str

    new_password: str = Field(
        ...,
        min_length=6
    )

    confirm_password: str = Field(
        ...,
        min_length=6
    )


class RefreshToken(BaseModel):
    """
    Refresh Access Token
    """

    refresh_token: str