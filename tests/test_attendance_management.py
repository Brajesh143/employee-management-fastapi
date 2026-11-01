from datetime import date, datetime, time
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
from models.attendance_policy import AttendancePolicy
from models.attendence import Attendance
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.shift import Shift
from routers.attendence import router as attendance_router
from services.attendance import build_attendance_report, compute_metrics


@pytest.fixture
def attendance_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        role = Role(name="Attendance Test")
        permission_names = {
            "attendance:create",
            "attendance:read",
            "attendance:wfh",
            "attendance:correct",
            "attendance:update",
            "employee:team:read",
            "report:read",
        }
        permissions = [
            Permission(name=name) for name in sorted(permission_names)
        ]
        manager = Employee(
            employee_code="MGR001",
            first_name="Team",
            last_name="Manager",
            email="manager@example.com",
            password_hash="",
            role=role,
        )
        db.add_all([role, *permissions, manager])
        db.flush()
        db.add_all(
            [
                RolePermission(role_id=role.id, permission_id=permission.id)
                for permission in permissions
            ]
        )
        employee = Employee(
            employee_code="EMP001",
            first_name="Team",
            last_name="Member",
            email="employee@example.com",
            password_hash="",
            role_id=role.id,
            reporting_manager_id=manager.id,
        )
        db.add(employee)
        db.commit()
        db.refresh(manager)
        db.refresh(employee)

    users = {
        "manager": SimpleNamespace(
            id=manager.id,
            role_id=manager.role_id,
            role=SimpleNamespace(name="Attendance Test"),
            reporting_manager_id=None,
            first_name="Team",
            last_name="Manager",
            shift_id=None,
        ),
        "employee": SimpleNamespace(
            id=employee.id,
            role_id=employee.role_id,
            role=SimpleNamespace(name="Attendance Test"),
            reporting_manager_id=manager.id,
            first_name="Team",
            last_name="Member",
            shift_id=None,
        ),
    }
    users["current"] = users["employee"]
    clock = {"now": datetime(2026, 1, 5, 10, 0)}
    app = FastAPI()
    app.include_router(attendance_router, prefix="/attendance")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: users["current"]
    monkeypatch.setattr(
        "services.attendance.current_datetime",
        lambda: clock["now"],
    )
    with TestClient(app) as client:
        yield client, engine, users, clock
    engine.dispose()


def test_compute_metrics_for_late_early_and_overnight_shifts():
    day_shift = Shift(
        name="Day",
        start_time=time(9, 0),
        end_time=time(18, 0),
        grace_minutes=30,
        unpaid_break_minutes=60,
    )
    metrics = compute_metrics(
        check_in=datetime(2026, 1, 5, 10, 0),
        check_out=datetime(2026, 1, 5, 16, 0),
        shift=day_shift,
    )
    assert metrics == {
        "late_minutes": 60,
        "early_leave_minutes": 120,
        "working_hours": 5.0,
        "overtime_hours": 0.0,
        "status": "Late",
    }

    night_shift = Shift(
        name="Night",
        start_time=time(22, 0),
        end_time=time(6, 0),
        grace_minutes=0,
        unpaid_break_minutes=30,
    )
    overnight = compute_metrics(
        check_in=datetime(2026, 1, 5, 22, 0),
        check_out=datetime(2026, 1, 6, 5, 0),
        shift=night_shift,
    )
    assert overnight["working_hours"] == 6.5
    assert overnight["early_leave_minutes"] == 60


def test_check_in_out_wfh_approval_and_attendance_correction(attendance_client):
    client, _, users, clock = attendance_client
    today = date(2026, 1, 5)

    past_wfh_response = client.post(
        "/attendance/wfh-requests",
        json={
            "request_date": date(2026, 1, 4).isoformat(),
            "reason": "Past date request",
        },
    )
    assert past_wfh_response.status_code == 400

    wfh_response = client.post(
        "/attendance/wfh-requests",
        json={"request_date": today.isoformat(), "reason": "Home appointment"},
    )
    assert wfh_response.status_code == 200
    wfh_request = wfh_response.json()

    users["current"] = users["manager"]
    approval = client.post(
        f"/attendance/wfh-requests/{wfh_request['id']}/approve",
        json={"comment": "Approved"},
    )
    assert approval.status_code == 200
    assert approval.json()["status"] == "Approved"

    users["current"] = users["employee"]
    check_in = client.post(
        "/attendance/check-in",
        json={"work_mode": "wfh", "source": "test"},
    )
    assert check_in.status_code == 200
    assert check_in.json()["work_mode"] == "wfh"
    assert check_in.json()["late_minutes"] == 60

    duplicate = client.post("/attendance/check-in", json={"work_mode": "office"})
    assert duplicate.status_code == 409

    clock["now"] = datetime(2026, 1, 5, 16, 0)
    check_out = client.post("/attendance/check-out", json={})
    assert check_out.status_code == 200
    assert check_out.json()["working_hours"] == 5
    assert check_out.json()["early_leave_minutes"] == 120

    correction = client.post(
        "/attendance/corrections",
        json={
            "original_attendance_id": check_in.json()["id"],
            "requested_check_in": "2026-01-05T09:00:00",
            "reason": "Forgot to clock in",
        },
    )
    assert correction.status_code == 200

    users["current"] = users["manager"]
    reviewed = client.post(
        f"/attendance/corrections/{correction.json()['id']}/approve",
        json={"comment": "Verified"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "Approved"

    users["current"] = users["employee"]
    updated = client.get("/attendance/today")
    assert updated.status_code == 200
    assert updated.json()["check_in"] == "2026-01-05T09:00:00"


def test_correction_request_requires_a_change():
    from schemas.attendence import CorrectionCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one attendance field"):
        CorrectionCreate(
            original_attendance_id=1,
            reason="No actual change",
        )

    normalized = CorrectionCreate(
        original_attendance_id=1,
        requested_check_in="2026-01-05T10:00:00+05:30",
        reason="Timezone normalization",
    )
    assert normalized.requested_check_in == datetime(2026, 1, 5, 4, 30)


def test_team_attendance_report_includes_manager_and_direct_reports(
    attendance_client,
):
    _, engine, users, _ = attendance_client
    with Session(engine) as db:
        policy = AttendancePolicy(allow_direct_wfh=False, weekend_days="5,6")
        db.add(policy)
        db.flush()

        manager = db.query(Employee).filter(Employee.id == users["manager"].id).one()
        employee = db.query(Employee).filter(Employee.id == users["employee"].id).one()
        unrelated = Employee(
            employee_code="EMP002",
            first_name="Other",
            last_name="Member",
            email="other@example.com",
            password_hash="",
            role_id=manager.role_id,
        )
        db.add(unrelated)
        db.flush()
        db.add(
            Attendance(
                employee_id=manager.id,
                attendance_date=date(2026, 1, 5),
                check_in=datetime(2026, 1, 5, 9, 0),
                working_hours=0,
                overtime_hours=0,
                status="Present",
                work_mode="office",
            )
        )
        db.commit()

        report = build_attendance_report(
            db,
            manager,
            start=date(2026, 1, 5),
            end=date(2026, 1, 5),
        )

        assert {row["employee_id"] for row in report["employees"]} == {
            manager.id,
            employee.id,
        }
