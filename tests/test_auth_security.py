import hashlib
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import main  # noqa: F401
from auth.dependencies import get_current_user
from auth.hashing import Hash
from auth.jwt import JWTHandler
from crud.auth import change_password, login_employee, revoke_access_token
from database import get_db
from database.database import Base
from models.employee import Employee
from schemas.auth import ChangePassword, LoginRequest


@pytest.fixture
def auth_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _legacy_hash(password: str) -> str:
    salt = "legacy-salt"
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def test_legacy_password_hash_is_verified_and_upgraded_on_login(
    auth_db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 64)
    password = "correct horse battery"
    employee = Employee(
        employee_code="AUTH001",
        first_name="Auth",
        last_name="Test",
        email="auth@example.com",
        password_hash=_legacy_hash(password),
        is_active=True,
    )
    auth_db.add(employee)
    auth_db.commit()

    result = login_employee(
        auth_db,
        LoginRequest(email="auth@example.com", password=password),
    )

    assert result["access_token"]
    assert employee.password_hash.startswith(("$2a$", "$2b$", "$2y$"))
    assert Hash.verify_password(password, employee.password_hash)


def test_logout_revokes_access_token_and_bad_subject_is_rejected(
    auth_db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", "b" * 64)
    employee = Employee(
        employee_code="AUTH002",
        first_name="Auth",
        last_name="Test",
        email="logout@example.com",
        password_hash=Hash.hash_password("correct horse battery"),
        is_active=True,
    )
    auth_db.add(employee)
    auth_db.commit()
    token = JWTHandler.create_access_token(
        {"sub": str(employee.id), "ver": employee.token_version}
    )

    assert get_current_user(token=token, db=auth_db).id == employee.id
    revoke_access_token(auth_db, token)

    with pytest.raises(HTTPException) as revoked_error:
        get_current_user(token=token, db=auth_db)
    assert revoked_error.value.status_code == 401

    malformed_token = JWTHandler.create_access_token(
        {"sub": "not-an-id", "ver": employee.token_version}
    )
    with pytest.raises(HTTPException) as subject_error:
        get_current_user(token=malformed_token, db=auth_db)
    assert subject_error.value.status_code == 401


def test_expired_tokens_are_rejected_and_password_hashes_use_bcrypt(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", "c" * 64)
    expired_token = JWTHandler.create_access_token(
        {"sub": "1", "ver": 0},
        expires_delta=timedelta(seconds=-1),
    )

    assert JWTHandler.verify_access_token(expired_token) is None

    hashed_password = Hash.hash_password("a sufficiently long password")
    assert hashed_password.startswith(("$2a$", "$2b$", "$2y$"))
    assert Hash.verify_password("a sufficiently long password", hashed_password)
    assert not Hash.verify_password("wrong password", hashed_password)


def test_password_change_invalidates_previously_issued_tokens(
    auth_db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", "d" * 64)
    employee = Employee(
        employee_code="AUTH003",
        first_name="Auth",
        last_name="Test",
        email="password@example.com",
        password_hash=Hash.hash_password("old password"),
        is_active=True,
    )
    auth_db.add(employee)
    auth_db.commit()
    token = JWTHandler.create_access_token(
        {"sub": str(employee.id), "ver": employee.token_version}
    )

    change_password(
        auth_db,
        employee,
        ChangePassword(
            current_password="old password",
            new_password="new password",
            confirm_password="new password",
        ),
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, db=auth_db)
    assert error.value.status_code == 401
    assert Hash.verify_password("new password", employee.password_hash)


def test_logout_endpoint_revokes_token_for_following_requests(
    auth_db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", "e" * 64)
    employee = Employee(
        employee_code="AUTH004",
        first_name="Auth",
        last_name="Test",
        email="endpoint@example.com",
        password_hash=Hash.hash_password("correct horse battery"),
        is_active=True,
    )
    auth_db.add(employee)
    auth_db.commit()

    def override_get_db():
        with Session(auth_db.get_bind()) as request_db:
            yield request_db

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(main.app) as client:
            login_response = client.post(
                "/auth/login",
                json={
                    "email": "endpoint@example.com",
                    "password": "correct horse battery",
                },
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            assert client.get("/auth/me", headers=headers).status_code == 200
            assert client.post("/auth/logout", headers=headers).status_code == 204
            assert client.get("/auth/me", headers=headers).status_code == 401
    finally:
        main.app.dependency_overrides.pop(get_db, None)


def test_jwt_signing_key_is_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        JWTHandler.create_access_token({"sub": "1", "ver": 0})
