import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import main  # noqa: F401
from database.database import Base
from models.attendence import Attendance
from models.employee import Employee
from models.leave import Leave
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.salary import Salary
from tools.report_tools import create_report_tools


def _create_employee(
    db: Session,
    code: str,
    permission_names: set[str],
) -> Employee:
    role = Role(name=f"{code} role")
    db.add(role)
    for permission_name in permission_names:
        permission = (
            db.query(Permission)
            .filter(Permission.name == permission_name)
            .first()
        )
        if permission is None:
            permission = Permission(
                name=permission_name,
                description=permission_name,
            )
            db.add(permission)
        db.flush()
        db.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id,
            )
        )
    employee = Employee(
        employee_code=code,
        first_name="Report",
        last_name="Employee",
        email=f"{code.lower()}@example.com",
        password_hash="test-hash",
        role_id=role.id,
        is_active=True,
    )
    db.add(employee)
    db.commit()
    return employee


def _report_tool(db: Session, employee_id: int):
    return create_report_tools(db, employee_id)[0]


def test_report_agent_returns_scoped_attendance_leave_and_payroll_aggregates():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        permissions = {
            "ai:admin",
            "report:read",
            "employee:read:all",
            "attendance:read",
            "leave:read",
            "salary:read",
        }
        admin = _create_employee(db, "RPT001", permissions)
        employee = _create_employee(db, "RPT002", set())
        db.add_all(
            [
                Attendance(
                    employee_id=employee.id,
                    attendance_date=date(2026, 3, 2),
                    check_in=datetime(2026, 3, 2, 9),
                    working_hours=8,
                    overtime_hours=1,
                    late_minutes=0,
                    status="Present",
                    work_mode="office",
                ),
                Leave(
                    employee_id=employee.id,
                    leave_type="Casual",
                    start_date=date(2026, 3, 3),
                    end_date=date(2026, 3, 4),
                    total_days=2,
                    reason="Family",
                    status="Approved",
                ),
                Salary(
                    employee_id=employee.id,
                    month=3,
                    year=2026,
                    basic_salary=5000,
                    hra=1000,
                    allowance=100,
                    bonus=200,
                    deduction=300,
                    tax=500,
                    net_salary=5500,
                    payment_status="Paid",
                ),
            ]
        )
        db.commit()

        tool = _report_tool(db, admin.id)
        attendance = tool.invoke(
            {
                "report_type": "attendance",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            }
        )
        attendance_data = json.loads(attendance)
        assert attendance_data["attendance"]["employees_in_scope"] == 2
        assert attendance_data["attendance"]["totals"]["present_days"] == 1

        leave = tool.invoke(
            {
                "report_type": "leave",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            }
        )
        leave_data = json.loads(leave)
        assert leave_data["leave"]["request_count"] == 1
        assert leave_data["leave"]["requested_days"] == 2

        payroll = tool.invoke(
            {
                "report_type": "payroll",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            }
        )
        payroll_data = json.loads(payroll)
        assert payroll_data["payroll"]["gross_pay"] == 6300
        assert payroll_data["payroll"]["deductions_and_tax"] == 800
        assert payroll_data["payroll"]["net_pay"] == 5500
        assert "employee_code" not in payroll_data["payroll"]

    engine.dispose()


def test_report_tool_requires_ai_admin_and_specific_data_permission():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(
            db,
            "RPT003",
            {"report:read", "attendance:read"},
        )
        assert create_report_tools(db, employee.id) == []

        admin = _create_employee(
            db,
            "RPT004",
            {"ai:admin", "report:read", "attendance:read"},
        )
        tool = _report_tool(db, admin.id)
        payroll_data = tool.invoke(
            {
                "report_type": "payroll",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            }
        )
        assert "Salary read permission is required" in payroll_data

    engine.dispose()


def test_report_tool_rejects_invalid_periods():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(
            db,
            "RPT005",
            {"ai:admin", "report:read", "leave:read"},
        )
        tool = _report_tool(db, employee.id)
        invalid_period = tool.invoke(
            {
                "report_type": "leave",
                "start_date": "2026-04-02",
                "end_date": "2026-04-01",
            }
        )
        long_period = tool.invoke(
            {
                "report_type": "leave",
                "start_date": "2025-01-01",
                "end_date": "2026-01-02",
            }
        )
        assert "on or after" in invalid_period
        assert "cannot exceed 366 days" in long_period

    engine.dispose()
