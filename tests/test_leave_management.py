from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main  # noqa: F401
from auth.dependencies import get_current_user
from database import get_db
from database.database import Base
from models.employee import Employee
from models.leave import Leave
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.leave import router as leave_router


@pytest.fixture
def leave_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee_role = Role(name="Leave Employee")
        manager_role = Role(name="Leave Manager")
        hr_role = Role(name="Leave HR")
        permissions_by_role = {
            employee_role: {"leave:create", "leave:read", "leave:cancel"},
            manager_role: {
                "leave:create",
                "leave:read",
                "leave:approve",
                "leave:cancel",
                "employee:team:read",
                "report:read",
            },
            hr_role: {
                "leave:create",
                "leave:read",
                "leave:approve",
                "leave:cancel",
                "leave:balance:manage",
                "employee:read:all",
                "report:read",
            },
        }
        all_permission_names = set().union(*permissions_by_role.values())
        permissions = {
            name: Permission(name=name) for name in all_permission_names
        }
        db.add_all(
            [
                employee_role,
                manager_role,
                hr_role,
                *permissions.values(),
            ]
        )
        db.flush()
        for role, permission_names in permissions_by_role.items():
            db.add_all(
                RolePermission(
                    role_id=role.id,
                    permission_id=permissions[name].id,
                )
                for name in permission_names
            )
        manager = Employee(
            employee_code="MGR001",
            first_name="Manager",
            last_name="Leave",
            email="manager.leave@example.com",
            password_hash="",
            role_id=manager_role.id,
            leave_balance=20,
        )
        hr = Employee(
            employee_code="HR001",
            first_name="HR",
            last_name="Reviewer",
            email="hr.leave@example.com",
            password_hash="",
            role_id=hr_role.id,
            leave_balance=20,
        )
        db.add_all([manager, hr])
        db.flush()
        employee = Employee(
            employee_code="EMP001",
            first_name="Employee",
            last_name="Leave",
            email="employee.leave@example.com",
            password_hash="",
            role_id=employee_role.id,
            reporting_manager_id=manager.id,
            leave_balance=20,
        )
        db.add(employee)
        db.commit()
        ids = {
            "employee": (employee.id, employee_role.id),
            "manager": (manager.id, manager_role.id),
            "hr": (hr.id, hr_role.id),
        }

    users = {
        name: SimpleNamespace(
            id=employee_id,
            role_id=role_id,
            role=SimpleNamespace(name=name),
            leave_balance=20,
            reporting_manager_id=(
                ids["manager"][0] if name == "employee" else None
            ),
        )
        for name, (employee_id, role_id) in ids.items()
    }
    users["current"] = users["employee"]
    app = FastAPI()
    app.include_router(leave_router, prefix="/leaves")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: users["current"]
    with TestClient(app) as client:
        yield client, engine, users
    engine.dispose()


def _request_payload(start: date, end: date | None = None) -> dict:
    return {
        "leave_type": "Casual",
        "start_date": start.isoformat(),
        "end_date": (end or start).isoformat(),
        "reason": "Personal leave",
    }


def test_leave_request_requires_manager_then_hr_and_refunds_on_cancellation(
    leave_client,
):
    client, engine, users = leave_client
    start = date.today() + timedelta(days=20)
    response = client.post("/leaves/", json=_request_payload(start, start + timedelta(days=1)))
    assert response.status_code == 201
    request = response.json()
    assert request["total_days"] == 2
    assert request["approval_stage"] == "manager"
    assert request["approval_manager_id"] == users["manager"].id

    overlapping = client.post("/leaves/", json=_request_payload(start))
    assert overlapping.status_code == 409

    users["current"] = users["manager"]
    manager_approval = client.put(f"/leaves/{request['id']}/approved")
    assert manager_approval.status_code == 200
    assert manager_approval.json()["leave"]["approval_stage"] == "hr"
    assert manager_approval.json()["leave"]["status"] == "Pending"

    manager_cannot_complete_hr_stage = client.put(
        f"/leaves/{request['id']}/approved"
    )
    assert manager_cannot_complete_hr_stage.status_code == 403

    users["current"] = users["hr"]
    hr_approval = client.put(f"/leaves/{request['id']}/approved")
    assert hr_approval.status_code == 200
    assert hr_approval.json()["leave"]["status"] == "Approved"
    assert hr_approval.json()["remaining_leave_balance"] == 18

    users["current"] = users["employee"]
    cancellation = client.post(
        f"/leaves/{request['id']}/cancel",
        json={"reason": "Plans changed"},
    )
    assert cancellation.status_code == 200
    assert cancellation.json()["status"] == "Cancelled"
    with Session(engine) as db:
        employee = db.query(Employee).filter_by(id=users["employee"].id).one()
        leave = db.query(Leave).filter_by(id=request["id"]).one()
        assert employee.leave_balance == 20
        assert leave.cancellation_reason == "Plans changed"


def test_leave_history_balance_reports_and_balance_management(leave_client):
    client, _, users = leave_client
    start = date.today() + timedelta(days=10)
    response = client.post("/leaves/", json=_request_payload(start))
    assert response.status_code == 201
    request = response.json()

    users["current"] = users["manager"]
    report = client.get(
        "/leaves/reports",
        params={"from": start.isoformat(), "to": start.isoformat()},
    )
    assert report.status_code == 200
    assert report.json()["totals"]["requests"] == 1
    assert report.json()["totals"]["pending"] == 1

    users["current"] = users["employee"]
    balance = client.get("/leaves/balance/me")
    assert balance.json() == {
        "employee_id": users["employee"].id,
        "leave_balance": 20,
    }
    history = client.get("/leaves/")
    assert [item["id"] for item in history.json()] == [request["id"]]

    users["current"] = users["hr"]
    update = client.patch(
        f"/leaves/balance/{users['employee'].id}",
        json={"leave_balance": 15},
    )
    assert update.status_code == 200
    assert update.json()["leave_balance"] == 15


def test_leave_rejection_is_terminal_and_hr_cannot_approve_own_request(
    leave_client,
):
    client, _, users = leave_client
    start = date.today() + timedelta(days=12)
    response = client.post("/leaves/", json=_request_payload(start))
    assert response.status_code == 201
    request = response.json()

    users["current"] = users["manager"]
    rejected = client.put(f"/leaves/{request['id']}/rejected")
    assert rejected.status_code == 200
    assert rejected.json()["leave"]["status"] == "Rejected"
    assert rejected.json()["leave"]["approval_stage"] == "rejected"

    users["current"] = users["hr"]
    own_request = client.post("/leaves/", json=_request_payload(start + timedelta(days=1)))
    assert own_request.status_code == 201
    self_approval = client.put(
        f"/leaves/{own_request.json()['id']}/approved"
    )
    assert self_approval.status_code == 404


def test_leave_create_rejects_invalid_date_ranges_and_client_employee_id(
    leave_client,
):
    client, _, _ = leave_client
    start = date.today() + timedelta(days=10)
    invalid = client.post(
        "/leaves/",
        json=_request_payload(start + timedelta(days=1), start),
    )
    assert invalid.status_code == 422

    forged_employee = client.post(
        "/leaves/",
        json={
            **_request_payload(start),
            "employee_id": 999,
        },
    )
    assert forged_employee.status_code == 422
