from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import main  # noqa: F401
from database.database import Base
from models.attendence import Attendance
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from tools.attendance_tools import create_attendance_tools


def _create_employee(db: Session, code: str, can_read_attendance: bool) -> Employee:
    role = Role(name=f"{code} role")
    db.add(role)
    if can_read_attendance:
        permission = (
            db.query(Permission)
            .filter(Permission.name == "attendance:read")
            .first()
        )
        if permission is None:
            permission = Permission(
                name="attendance:read",
                description="Read attendance",
            )
            db.add(permission)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    employee = Employee(
        employee_code=code,
        first_name="Attendance",
        last_name="Employee",
        email=f"{code.lower()}@example.com",
        password_hash="test-hash",
        role_id=role.id,
    )
    db.add(employee)
    db.commit()
    return employee


def test_attendance_agent_returns_scoped_history_and_month_summary():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(db, "ATT001", can_read_attendance=True)
        other_employee = _create_employee(db, "ATT002", can_read_attendance=True)
        db.add_all(
            [
                Attendance(
                    employee_id=employee.id,
                    attendance_date=date(2026, 8, 3),
                    check_in=datetime(2026, 8, 3, 9),
                    check_out=datetime(2026, 8, 3, 18),
                    working_hours=8,
                    overtime_hours=1,
                    late_minutes=0,
                    status="Present",
                    work_mode="office",
                ),
                Attendance(
                    employee_id=employee.id,
                    attendance_date=date(2026, 8, 4),
                    check_in=datetime(2026, 8, 4, 9, 20),
                    working_hours=7.5,
                    overtime_hours=0,
                    late_minutes=20,
                    status="Late",
                    work_mode="wfh",
                ),
                Attendance(
                    employee_id=employee.id,
                    attendance_date=date(2026, 8, 5),
                    check_in=datetime(2026, 8, 5, 9),
                    working_hours=0,
                    overtime_hours=0,
                    late_minutes=0,
                    status="Absent",
                    work_mode="office",
                ),
                Attendance(
                    employee_id=other_employee.id,
                    attendance_date=date(2026, 8, 6),
                    check_in=datetime(2026, 8, 6, 9),
                    working_hours=8,
                    overtime_hours=0,
                    late_minutes=0,
                    status="Present",
                    work_mode="office",
                ),
            ]
        )
        db.commit()

        tools = {
            available_tool.name: available_tool
            for available_tool in create_attendance_tools(db, employee.id)
        }
        result = tools["get_my_attendance_history"].invoke(
            {"month": 8, "year": 2026}
        )

        assert result["month"] == "August"
        assert result["summary"] == {
            "recorded_days": 3,
            "present_days": 2,
            "absent_days": 1,
            "late_days": 1,
            "work_from_home_days": 1,
            "working_hours": 15.5,
            "overtime_hours": 1,
        }
        assert len(result["records"]) == 3
        assert all(
            record["date"] != "2026-08-06"
            for record in result["records"]
        )

    engine.dispose()


def test_attendance_agent_today_reports_record_or_missing_record(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(db, "ATT003", can_read_attendance=True)
        monkeypatch.setattr(
            "tools.attendance_tools.current_datetime",
            lambda: datetime(2026, 8, 10, 10),
        )
        tools = {
            available_tool.name: available_tool
            for available_tool in create_attendance_tools(db, employee.id)
        }
        missing = tools["get_my_attendance_today"].invoke({})
        assert missing == {
            "date": "2026-08-10",
            "has_attendance_record": False,
            "message": "No attendance record has been created for today.",
        }

        db.add(
            Attendance(
                employee_id=employee.id,
                attendance_date=date(2026, 8, 10),
                check_in=datetime(2026, 8, 10, 9),
                status="Present",
                work_mode="office",
            )
        )
        db.commit()
        record = tools["get_my_attendance_today"].invoke({})
        assert record["has_attendance_record"] is True
        assert record["status"] == "Present"
        assert record["check_in"] == "2026-08-10T09:00:00"
        assert record["check_out"] is None

    engine.dispose()


def test_attendance_tools_are_hidden_without_read_permission():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(db, "ATT004", can_read_attendance=False)
        assert create_attendance_tools(db, employee.id) == []

    engine.dispose()


@pytest.mark.parametrize(
    ("month", "year", "message"),
    [
        (0, 2026, "Month must be between 1 and 12"),
        (13, 2026, "Month must be between 1 and 12"),
        (1, 1999, "Year must be between 2000 and 2100"),
        (1, 2101, "Year must be between 2000 and 2100"),
    ],
)
def test_attendance_history_validates_month_and_year(month, year, message):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(db, "ATT005", can_read_attendance=True)
        tools = create_attendance_tools(db, employee.id)
        history_tool = next(
            available_tool
            for available_tool in tools
            if available_tool.name == "get_my_attendance_history"
        )
        assert history_tool.invoke({"month": month, "year": year}) == {
            "error": message + "."
        }

    engine.dispose()
