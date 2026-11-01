import io
from datetime import date
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main  # noqa: F401
from auth.dependencies import get_current_user
from database import get_db
from database.database import Base
from models.attendence import Attendance
from models.department import Department
from models.employee import Employee
from models.leave import Leave
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.salary import Salary
from routers.reports import router as reports_router


@pytest.fixture
def reports_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    permissions_by_role = {
        "Analytics Admin": {
            "report:read",
            "employee:read",
            "employee:read:all",
            "attendance:read",
            "leave:read",
            "salary:read",
        },
        "Analytics Finance": {"report:read", "salary:read"},
        "Analytics Employee": {"report:read"},
    }

    with Session(engine) as db:
        roles = {name: Role(name=name) for name in permissions_by_role}
        permissions = {
            name: Permission(name=name)
            for name in set().union(*permissions_by_role.values())
        }
        db.add_all([*roles.values(), *permissions.values()])
        db.flush()
        db.add_all(
            RolePermission(
                role_id=roles[role_name].id,
                permission_id=permissions[permission_name].id,
            )
            for role_name, names in permissions_by_role.items()
            for permission_name in names
        )
        department = Department(name="Analytics Engineering", is_active=True)
        db.add(department)
        db.flush()
        active = Employee(
            employee_code="ANL001",
            first_name="Alex",
            last_name="Active",
            email="alex.analytics@example.com",
            password_hash="",
            role_id=roles["Analytics Admin"].id,
            department_id=department.id,
            joining_date=date(2025, 1, 1),
            is_active=True,
        )
        exited = Employee(
            employee_code="ANL002",
            first_name="Erin",
            last_name="Exited",
            email="erin.analytics@example.com",
            password_hash="",
            role_id=roles["Analytics Admin"].id,
            department_id=department.id,
            joining_date=date(2024, 1, 1),
            is_active=False,
            exit_date=date(2026, 2, 1),
            exit_reason="Resigned",
        )
        finance = Employee(
            employee_code="ANL003",
            first_name="Frank",
            last_name="Finance",
            email="frank.analytics@example.com",
            password_hash="",
            role_id=roles["Analytics Finance"].id,
            is_active=True,
        )
        report_only = Employee(
            employee_code="ANL004",
            first_name="Rory",
            last_name="Restricted",
            email="rory.analytics@example.com",
            password_hash="",
            role_id=roles["Analytics Employee"].id,
            is_active=True,
        )
        db.add_all([active, exited, finance, report_only])
        db.flush()
        db.add(
            Attendance(
                employee_id=active.id,
                attendance_date=date(2026, 2, 2),
                check_in=datetime(2026, 2, 2, 9),
                status="Present",
                work_mode="office",
                source="test",
            )
        )
        db.add(
            Leave(
                employee_id=active.id,
                leave_type="Casual",
                start_date=date(2026, 2, 3),
                end_date=date(2026, 2, 4),
                total_days=2,
                reason="Personal",
                status="Approved",
            )
        )
        db.add(
            Salary(
                employee_id=active.id,
                month=2,
                year=2026,
                basic_salary=5000,
                hra=1000,
                allowance=200,
                bonus=100,
                deduction=200,
                tax=300,
                net_salary=5800,
                payment_status="Paid",
            )
        )
        db.commit()
        users = {
            "admin": SimpleNamespace(
                id=active.id,
                role_id=active.role_id,
                role=SimpleNamespace(name="Analytics Admin"),
                reporting_manager_id=None,
            ),
            "finance": SimpleNamespace(
                id=finance.id,
                role_id=finance.role_id,
                role=SimpleNamespace(name="Analytics Finance"),
                reporting_manager_id=None,
            ),
            "report_only": SimpleNamespace(
                id=report_only.id,
                role_id=report_only.role_id,
                role=SimpleNamespace(name="Analytics Employee"),
                reporting_manager_id=None,
            ),
        }

    users["current"] = users["admin"]
    app = FastAPI()
    app.include_router(reports_router, prefix="/reports")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: users["current"]
    with TestClient(app) as client:
        yield client, users
    engine.dispose()


def test_analytics_returns_scoped_employee_attendance_leave_and_payroll_reports(
    reports_client,
):
    client, _ = reports_client
    response = client.get(
        "/reports/analytics?from=2026-02-01&to=2026-02-28"
    )
    assert response.status_code == 200
    report = response.json()
    assert report["employees"]["active"] == 3
    assert report["employees"]["hires_in_period"] == 0
    assert report["attendance"]["totals"]["present_days"] == 1
    assert report["leaves"]["totals"]["approved"] == 1
    assert report["leaves"]["totals"]["requested_days"] == 2
    assert report["payroll"]["gross_pay"] == 6300
    assert report["payroll"]["net_pay"] == 5800
    assert report["attrition"]["opening_headcount"] == 2
    assert report["attrition"]["exits_in_period"] == 1
    assert report["attrition"]["attrition_rate_percent"] == 50
    assert report["departments"][0]["department"] == "Analytics Engineering"
    assert report["departments"][0]["exits_in_period"] == 1


def test_payroll_report_and_exports_enforce_permissions_and_download_formats(
    reports_client,
):
    client, users = reports_client
    users["current"] = users["finance"]
    finance_report = client.get(
        "/reports/analytics?from=2026-02-01&to=2026-02-28"
    )
    assert finance_report.status_code == 200
    data = finance_report.json()
    assert data["payroll"]["net_pay"] == 5800
    assert "employees" not in data
    assert "attrition" not in data
    assert "attendance" not in data

    csv_response = client.get(
        "/reports/payroll/export"
        "?from=2026-02-01&to=2026-02-28&format=csv"
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "gross_pay" in csv_response.text
    assert "6300.0" in csv_response.text

    pdf_response = client.get(
        "/reports/payroll/export"
        "?from=2026-02-01&to=2026-02-28&format=pdf"
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-1.4")
    pdf_reader = PdfReader(io.BytesIO(pdf_response.content))
    assert "Payroll Report" in pdf_reader.pages[0].extract_text()

    users["current"] = users["admin"]
    empty_attrition = client.get(
        "/reports/attrition/export"
        "?from=2026-03-01&to=2026-03-31&format=csv"
    )
    assert empty_attrition.status_code == 200
    assert "employee_code" in empty_attrition.text

    users["current"] = users["report_only"]
    denied = client.get(
        "/reports/payroll/export"
        "?from=2026-02-01&to=2026-02-28&format=csv"
    )
    assert denied.status_code == 403
