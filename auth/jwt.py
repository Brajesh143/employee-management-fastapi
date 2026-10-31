import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
TOKEN_ISSUER = "employee-management"
TOKEN_AUDIENCE = "employee-management-api"


def _secret_key() -> str:
    secret_key = os.getenv("JWT_SECRET_KEY", "")
    if len(secret_key.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured with at least 32 bytes. "
            "Generate one with: openssl rand -hex 32"
        )
    return secret_key


class JWTHandler:
    """
    Handles JWT token creation and verification.
    """

    @staticmethod
    def validate_configuration() -> None:
        _secret_key()

    @staticmethod
    def create_access_token(
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + (
            expires_delta
            if expires_delta is not None
            else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update(
            {
                "iat": now,
                "exp": expire,
                "jti": uuid4().hex,
                "iss": TOKEN_ISSUER,
                "aud": TOKEN_AUDIENCE,
            }
        )
        return jwt.encode(to_encode, _secret_key(), algorithm=ALGORITHM)

    @staticmethod
    def verify_access_token(token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(
                token,
                _secret_key(),
                algorithms=[ALGORITHM],
                issuer=TOKEN_ISSUER,
                audience=TOKEN_AUDIENCE,
                options={
                    "require_sub": True,
                    "require_exp": True,
                    "require_iat": True,
                },
            )
        except JWTError:
            return None