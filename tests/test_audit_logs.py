from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from auth.dependencies import get_current_user
from crud.employee import update_employee
from database import get_db
from database.database import Base
from models.audit_log import AuditLog
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.audit import router as audit_router
from schemas.employee import EmployeeUpdate
from services.audit import employee_audit_snapshot, write_audit_log


@pytest.fixture
def audit_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        role = Role(name="Auditor")
        permission = Permission(name="audit:read")
        db.add_all([role, permission])
        db.flush()
        actor = Employee(
            employee_code="AUD001",
            first_name="Audit",
            last_name="User",
            email="audit@example.com",
            password_hash="",
            role_id=role.id,
        )
        db.add(actor)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        write_audit_log(
            db,
            actor_id=actor.id,
            action="employee.update",
            resource_type="employee",
            resource_id=9,
            before={"status": "Active"},
            after={"status": "Inactive"},
        )
        write_audit_log(
            db,
            actor_id=actor.id,
            action="role.create",
            resource_type="role",
            resource_id=3,
            after={"name": "Custom"},
        )
        db.commit()
        actor_id = actor.id

    app = FastAPI()
    app.include_router(audit_router, prefix="/audit-logs")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=actor_id,
        role_id=1,
        role=SimpleNamespace(name="Auditor"),
        is_active=True,
    )
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def test_audit_endpoint_filters_and_paginates(audit_client):
    client, _ = audit_client
    response = client.get(
        "/audit-logs/",
        params={
            "action": "employee",
            "resource_type": "employee",
            "actor_id": 1,
            "page": 1,
            "page_size": 1,
            "from": "2020-01-01",
            "to": "2030-01-01",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "1"
    assert len(response.json()) == 1
    assert response.json()[0]["action"] == "employee.update"
    assert response.json()[0]["before_json"] == '{"status": "Active"}'


def test_audit_endpoint_rejects_reversed_date_range(audit_client):
    client, _ = audit_client
    response = client.get(
        "/audit-logs/",
        params={"from": "2030-01-02", "to": "2030-01-01"},
    )
    assert response.status_code == 422


def test_audit_endpoint_requires_audit_read_permission(audit_client):
    client, _ = audit_client
    client.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        role_id=999,
        role=SimpleNamespace(name="Employee"),
        is_active=True,
    )

    response = client.get("/audit-logs/")

    assert response.status_code == 403


def test_employee_snapshots_omit_password_data():
    employee = SimpleNamespace(
        id=4,
        employee_code="EMP004",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        department_id=None,
        designation_id=None,
        role_id=None,
        reporting_manager_id=None,
        is_active=True,
        status="Active",
        exit_date=None,
        exit_reason=None,
        password_hash="must-not-be-recorded",
    )

    snapshot = employee_audit_snapshot(employee)
    assert "password_hash" not in snapshot


def test_employee_update_records_before_and_after_without_password(audit_client):
    _, engine = audit_client
    with Session(engine) as db:
        target = Employee(
            employee_code="EMP009",
            first_name="Target",
            last_name="Employee",
            email="target@example.com",
            password_hash="not-recorded",
            status="Active",
        )
        db.add(target)
        db.flush()
        actor_id = (
            db.query(Employee.id)
            .filter(Employee.email == "audit@example.com")
            .scalar()
        )

        updated = update_employee(
            target.id,
            EmployeeUpdate(status="Inactive"),
            db,
            actor_id=actor_id,
        )
        log = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "employee.update",
                AuditLog.resource_id == target.id,
            )
            .order_by(AuditLog.id.desc())
            .first()
        )

        assert updated.status == "Inactive"
        assert log is not None
        assert '"status": "Active"' in log.before_json
        assert '"status": "Inactive"' in log.after_json
        assert "not-recorded" not in (log.before_json or "") + (log.after_json or "")
