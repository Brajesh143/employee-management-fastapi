import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main  # noqa: F401
from auth.hashing import Hash
from database import get_db
from database.database import Base
from models.employee import Employee
from routers.auth import router as auth_router


@pytest.fixture
def password_change_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        db.add(
            Employee(
                employee_code="CHANGE001",
                first_name="Change",
                last_name="User",
                email="change@example.com",
                password_hash=Hash.hash_password("old-password"),
                is_active=True,
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_password_change_requires_login_and_invalidates_old_session(
    password_change_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "reset-test-key-0123456789abcdef0123456789abcdef",
    )
    payload = {
        "current_password": "old-password",
        "new_password": "new-strong-password",
        "confirm_password": "new-strong-password",
    }

    unauthorized = password_change_client.put(
        "/auth/change-password",
        json=payload,
    )
    assert unauthorized.status_code == 401

    login_response = password_change_client.post(
        "/auth/login",
        json={"email": "change@example.com", "password": "old-password"},
    )
    assert login_response.status_code == 200
    old_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {old_token}"}

    change_response = password_change_client.put(
        "/auth/change-password",
        json=payload,
        headers=headers,
    )
    assert change_response.status_code == 200
    assert change_response.json()["message"] == "Password changed successfully"
    assert password_change_client.get("/auth/me", headers=headers).status_code == 401

    new_login = password_change_client.post(
        "/auth/login",
        json={
            "email": "change@example.com",
            "password": "new-strong-password",
        },
    )
    assert new_login.status_code == 200


def test_email_password_reset_routes_are_disabled(
    password_change_client: TestClient,
):
    assert password_change_client.post(
        "/auth/forgot-password",
        json={"email": "change@example.com"},
    ).status_code == 404
    assert password_change_client.post(
        "/auth/reset-password",
        json={
            "token": "unused",
            "new_password": "new-strong-password",
            "confirm_password": "new-strong-password",
        },
    ).status_code == 404
