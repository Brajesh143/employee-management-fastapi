from datetime import date
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
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.expense import router as expense_router
from routers.salary import router as salary_router
from services.employee_document_storage import LocalDiskDocumentStorage


@pytest.fixture
def payroll_expense_client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    permissions_by_role = {
        "Employee": {"expense:create", "expense:read", "payslip:read"},
        "Manager": {
            "employee:team:read",
            "expense:create",
            "expense:read",
            "expense:approve",
        },
        "Finance": {
            "salary:create",
            "salary:read",
            "payroll:generate",
            "payslip:read",
            "expense:read",
            "reimbursement:approve",
        },
    }

    with Session(engine) as db:
        roles = {
            name: Role(name=f"{name} Payroll Expense Test")
            for name in permissions_by_role
        }
        permission_names = set().union(*permissions_by_role.values())
        permissions = {
            name: Permission(name=name) for name in permission_names
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

        manager = Employee(
            employee_code="MGR-PAY",
            first_name="Morgan",
            last_name="Manager",
            email="manager.payroll@example.com",
            password_hash="",
            role_id=roles["Manager"].id,
        )
        finance = Employee(
            employee_code="FIN-PAY",
            first_name="Finley",
            last_name="Finance",
            email="finance.payroll@example.com",
            password_hash="",
            role_id=roles["Finance"].id,
        )
        db.add_all([manager, finance])
        db.flush()
        employee = Employee(
            employee_code="EMP-PAY",
            first_name="Elliot",
            last_name="Employee",
            email="employee.payroll@example.com",
            password_hash="",
            role_id=roles["Employee"].id,
            reporting_manager_id=manager.id,
        )
        db.add(employee)
        db.commit()
        users = {
            name.lower(): SimpleNamespace(
                id=record.id,
                role_id=record.role_id,
                role=SimpleNamespace(name=name),
                reporting_manager_id=record.reporting_manager_id,
            )
            for name, record in (
                ("Employee", employee),
                ("Manager", manager),
                ("Finance", finance),
            )
        }
    users["current"] = users["employee"]

    app = FastAPI()
    app.include_router(salary_router, prefix="/salaries")
    app.include_router(expense_router, prefix="/expenses")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: users["current"]
    monkeypatch.setattr(
        "routers.expense.get_document_storage",
        lambda: LocalDiskDocumentStorage(tmp_path),
    )
    with TestClient(app) as client:
        yield client, engine, users
    engine.dispose()


def test_salary_structure_generates_payroll_and_employee_can_download_payslip(
    payroll_expense_client,
):
    client, _, users = payroll_expense_client
    users["current"] = users["finance"]
    structure_response = client.post(
        "/salaries/structures",
        json={
            "employee_id": users["employee"].id,
            "basic_salary": 5000,
            "hra": 1000,
            "allowance": 500,
            "recurring_deduction": 200,
            "tax_rate": 10,
            "effective_from": "2026-01-01",
        },
    )
    assert structure_response.status_code == 201

    payroll_response = client.post(
        "/salaries/payroll/generate?month=1&year=2026"
    )
    assert payroll_response.status_code == 200
    payroll = payroll_response.json()
    assert payroll["generated_count"] == 1
    assert payroll["skipped_count"] == 2
    assert payroll["total_net_pay"] == 5650
    salary_id = payroll["salaries"][0]["id"]

    users["current"] = users["employee"]
    payslip_response = client.get(f"/salaries/{salary_id}/payslip")
    assert payslip_response.status_code == 200
    assert payslip_response.json()["employee_code"] == "EMP-PAY"
    assert payslip_response.json()["net_salary"] == 5650

    download_response = client.get(f"/salaries/{salary_id}/payslip/download")
    assert download_response.status_code == 200
    assert "Employee Payslip" in download_response.text
    assert "2026-01" in download_response.text

    users["current"] = users["finance"]
    paid_response = client.patch(
        f"/salaries/{salary_id}",
        json={"payment_status": "Paid", "payment_date": "2026-02-01"},
    )
    assert paid_response.status_code == 200
    assert paid_response.json()["payment_status"] == "Paid"


def test_expense_receipt_approval_and_reimbursement_lifecycle(
    payroll_expense_client,
):
    client, _, users = payroll_expense_client
    claim_response = client.post(
        "/expenses/",
        json={
            "expense_date": date.today().isoformat(),
            "category": "Travel",
            "amount": 125.5,
            "description": "Taxi to customer site",
        },
    )
    assert claim_response.status_code == 201
    claim_id = claim_response.json()["id"]

    users["current"] = users["manager"]
    missing_receipt = client.post(
        f"/expenses/{claim_id}/approve",
        json={"comment": "Reviewed"},
    )
    assert missing_receipt.status_code == 409

    users["current"] = users["employee"]
    receipt_response = client.post(
        f"/expenses/{claim_id}/receipt",
        files={"file": ("receipt.pdf", b"%PDF-1.7\nreceipt", "application/pdf")},
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["receipt_name"] == "receipt.pdf"

    users["current"] = users["manager"]
    approval_response = client.post(
        f"/expenses/{claim_id}/approve",
        json={"comment": "Approved"},
    )
    assert approval_response.status_code == 200
    assert approval_response.json()["status"] == "Approved"
    assert approval_response.json()["reimbursement_status"] == "Pending"

    users["current"] = users["finance"]
    reimbursement_response = client.post(
        f"/expenses/{claim_id}/reimburse"
    )
    assert reimbursement_response.status_code == 200
    assert reimbursement_response.json()["reimbursement_status"] == "Paid"

    receipt_download = client.get(f"/expenses/{claim_id}/receipt")
    assert receipt_download.status_code == 200
    assert receipt_download.content.startswith(b"%PDF-1.7")

    duplicate_reimbursement = client.post(
        f"/expenses/{claim_id}/reimburse"
    )
    assert duplicate_reimbursement.status_code == 409
