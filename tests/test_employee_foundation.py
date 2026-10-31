import csv
import importlib.util
import io
import stat
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from auth.dependencies import get_current_user
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from crud.employee import get_employees, update_employee
from database import get_db
from database.database import Base
from models.designation import Designation
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from schemas.employee import EmployeeUpdate
from services.employee_csv import export_employees_csv, preview_employee_csv
from services.employee_document_storage import LocalDiskDocumentStorage
from services.employee_documents import create_employee_document, get_employee_documents
from routers.designation import router as designation_router
from routers.employee import router as employee_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def add_employee(db: Session, code: str, **kwargs) -> Employee:
    employee = Employee(
        employee_code=code,
        first_name=kwargs.pop("first_name", "Test"),
        last_name=kwargs.pop("last_name", code),
        email=kwargs.pop("email", f"{code.lower()}@example.com"),
        password_hash="",
        **kwargs,
    )
    db.add(employee)
    db.flush()
    return employee


@pytest.fixture
def employee_api(tmp_path, monkeypatch):
    monkeypatch.setenv("EMPLOYEE_DOCUMENTS_DIR", str(tmp_path / "documents"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_user = SimpleNamespace(
        id=1,
        role_id=1,
        role=SimpleNamespace(name="API Test"),
        is_active=True,
    )
    with Session(engine) as db:
        db.add(Role(id=1, name="API Test"))
        permissions = [
            Permission(name=name, description="Test permission")
            for name in (
                "employee:read",
                "employee:read:all",
                "employee:create",
                "employee:export",
                "employee:import",
                "employee:update",
                "document:manage",
            )
        ]
        db.add_all(permissions)
        db.flush()
        db.add_all(
            [
                RolePermission(role_id=1, permission_id=permission.id)
                for permission in permissions
            ]
        )
        db.commit()
    app = FastAPI()
    app.include_router(employee_router, prefix="/employees")
    app.include_router(designation_router, prefix="/designations")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as client:
        yield client, engine, test_user
    engine.dispose()


def test_employee_list_filters_sorts_and_paginates(db_session: Session):
    manager = add_employee(db_session, "EMP001", first_name="Amina")
    add_employee(
        db_session,
        "EMP003",
        first_name="Chandra",
        reporting_manager_id=manager.id,
    )
    add_employee(
        db_session,
        "EMP002",
        first_name="Bala",
        reporting_manager_id=manager.id,
    )

    page, total = get_employees(
        db_session,
        page=1,
        page_size=1,
        sort_by="employee_code",
        sort_order="desc",
        reporting_manager_id=manager.id,
        q="EMP",
    )

    assert total == 2
    assert [employee.employee_code for employee in page] == ["EMP003"]


def test_employee_manager_assignment_rejects_cycles(db_session: Session):
    manager = add_employee(db_session, "EMP001")
    employee = add_employee(
        db_session,
        "EMP002",
        reporting_manager_id=manager.id,
    )

    with pytest.raises(ValueError, match="cycle"):
        update_employee(
            manager.id,
            EmployeeUpdate(reporting_manager_id=employee.id),
            db_session,
        )


def test_employee_can_be_assigned_an_active_manager_and_designation(
    db_session: Session,
):
    manager = add_employee(db_session, "MGR001")
    designation = Designation(name="Engineer", is_active=True)
    db_session.add(designation)
    db_session.flush()
    employee = add_employee(db_session, "EMP001")

    updated = update_employee(
        employee.id,
        EmployeeUpdate(
            reporting_manager_id=manager.id,
            designation_id=designation.id,
        ),
        db_session,
    )

    assert updated.reporting_manager_id == manager.id
    assert updated.designation_id == designation.id


def test_inactive_designation_cannot_be_assigned(db_session: Session):
    designation = Designation(name="Engineer", is_active=False)
    db_session.add(designation)
    employee = add_employee(db_session, "EMP001")

    with pytest.raises(ValueError, match="active"):
        update_employee(
            employee.id,
            EmployeeUpdate(designation_id=designation.id),
            db_session,
        )


def test_document_upload_uses_local_storage_and_metadata(db_session: Session, tmp_path):
    employee = add_employee(db_session, "EMP001")
    storage = LocalDiskDocumentStorage(tmp_path)

    document = create_employee_document(
        db_session,
        employee,
        r"C:\uploads\contract.pdf",
        b"%PDF-1.7\ncontract",
        storage,
    )

    assert document.file_name == "contract.pdf"
    assert document.content_type == "application/pdf"
    assert document.file_size == len(b"%PDF-1.7\ncontract")
    assert get_employee_documents(db_session, employee.id) == [document]
    stored_path = tmp_path / document.storage_key
    assert stat.S_IMODE(stored_path.stat().st_mode) == 0o600
    with storage.open(document.storage_key) as stored_file:
        assert stored_file.read() == b"%PDF-1.7\ncontract"

    with pytest.raises(ValueError, match="storage key"):
        storage.open("../outside.pdf")


def test_document_upload_rejects_content_extension_mismatch(
    db_session: Session,
    tmp_path,
):
    employee = add_employee(db_session, "EMP001")

    with pytest.raises(ValueError, match="valid PDF"):
        create_employee_document(
            db_session,
            employee,
            "fake.pdf",
            b"not a pdf",
            LocalDiskDocumentStorage(tmp_path),
        )


def test_csv_import_preview_validates_without_inserting_employees(db_session: Session):
    add_employee(
        db_session,
        "EMP001",
        email="existing@example.com",
    )
    content = (
        "employee_code,first_name,last_name,email,joining_date\n"
        "EMP002,New,Employee,new@example.com,2026-01-15\n"
        "EMP003,Dupe,One,duplicate@example.com,\n"
        "EMP003,Dupe,Two,duplicate@example.com,\n"
    ).encode()

    preview = preview_employee_csv(db_session, content)

    assert preview.total_rows == 3
    assert preview.valid_rows == 1
    assert preview.invalid_rows == 2
    assert preview.rows[1].valid is False
    assert preview.rows[2].valid is False
    assert db_session.query(Employee).count() == 1


def test_csv_import_preview_rejects_existing_identifiers(db_session: Session):
    add_employee(
        db_session,
        "EMP001",
        email="existing@example.com",
    )
    content = (
        "employee_code,first_name,last_name,email\n"
        "EMP001,Existing,Code,new@example.com\n"
        "EMP002,Existing,Email,existing@example.com\n"
    ).encode()

    preview = preview_employee_csv(db_session, content)

    assert preview.valid_rows == 0
    assert preview.invalid_rows == 2


def test_employee_csv_export_escapes_spreadsheet_formulas(db_session: Session):
    add_employee(
        db_session,
        "EMP001",
        first_name="=1+1",
        email="employee@example.com",
        joining_date=date(2026, 1, 15),
    )
    employee = db_session.query(Employee).one()

    rows = list(csv.reader(io.StringIO(export_employees_csv([employee]))))

    assert rows[1][1] == "'=1+1"
    assert rows[1][6] == "2026-01-15"


def test_employee_foundation_migration_runs_on_sqlite():
    engine = create_engine("sqlite:///:memory:")
    migration_path = (
        PROJECT_ROOT
        / "alembic"
        / "versions"
        / "d7a21f95c6b4_employee_foundation_phase.py"
    )
    spec = importlib.util.spec_from_file_location(
        "employee_foundation_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE departments (id INTEGER NOT NULL PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE roles (id INTEGER NOT NULL PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE employees ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "department_id INTEGER, "
            "role_id INTEGER, "
            "FOREIGN KEY(department_id) REFERENCES departments(id), "
            "FOREIGN KEY(role_id) REFERENCES roles(id))"
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(employees)")
        }
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        downgraded_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(employees)")
        }
        downgraded_tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"designation_id", "exit_date", "exit_reason"} <= columns
    assert {"designations", "employee_documents"} <= tables
    assert not {"designation_id", "exit_date", "exit_reason"} & downgraded_columns
    assert not {"designations", "employee_documents"} & downgraded_tables


def test_attendance_migration_reconciles_tables_already_created_by_application():
    engine = create_engine("sqlite:///:memory:")
    migration_path = (
        PROJECT_ROOT
        / "alembic"
        / "versions"
        / "c4e8f1a92b70_attendance_management_phase.py"
    )
    spec = importlib.util.spec_from_file_location(
        "attendance_management_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE departments (id INTEGER NOT NULL PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE roles (id INTEGER NOT NULL PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE employees ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "department_id INTEGER, "
            "role_id INTEGER, "
            "FOREIGN KEY(department_id) REFERENCES departments(id), "
            "FOREIGN KEY(role_id) REFERENCES roles(id))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE attendance ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "employee_id INTEGER NOT NULL, "
            "attendance_date DATE NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE shifts ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "name VARCHAR(100) NOT NULL UNIQUE, "
            "start_time TIME NOT NULL, "
            "end_time TIME NOT NULL, "
            "grace_minutes INTEGER NOT NULL, "
            "unpaid_break_minutes INTEGER NOT NULL, "
            "is_default BOOLEAN NOT NULL, "
            "is_active BOOLEAN NOT NULL, "
            "created_at DATETIME, "
            "updated_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO shifts "
            "(id, name, start_time, end_time, grace_minutes, unpaid_break_minutes, "
            "is_default, is_active) "
            "VALUES (1, 'Existing Shift', '09:00', '18:00', 30, 60, 1, 1)"
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        employee_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(employees)")
        }
        employee_foreign_keys = {
            row[2] for row in connection.exec_driver_sql("PRAGMA foreign_key_list(employees)")
        }
        attendance_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(attendance)")
        }
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        shift = connection.exec_driver_sql(
            "SELECT name FROM shifts WHERE id = 1"
        ).scalar_one()

    assert {"reporting_manager_id", "shift_id"} <= employee_columns
    assert {"departments", "roles", "shifts", "employees"} <= employee_foreign_keys
    assert {
        "late_minutes",
        "early_leave_minutes",
        "work_mode",
        "source",
        "notes",
        "shift_id",
    } <= attendance_columns
    assert {"wfh_requests", "attendance_corrections"} <= tables
    assert shift == "Existing Shift"


def test_employee_api_filters_paginates_exports_and_previews(employee_api):
    client, engine, _ = employee_api
    with Session(engine) as db:
        add_employee(db, "EMP001", first_name="Amina")
        add_employee(db, "EMP002", first_name="Bala")
        db.commit()

    response = client.get(
        "/employees/",
        params={"q": "EMP", "page": 1, "page_size": 1, "sort_by": "employee_code"},
    )
    assert response.status_code == 200
    assert [row["employee_code"] for row in response.json()] == ["EMP001"]
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Page"] == "1"

    export = client.get("/employees/export", params={"q": "EMP002"})
    assert export.status_code == 200
    assert "EMP002" in export.text
    assert "EMP001" not in export.text
    assert export.headers["content-type"].startswith("text/csv")

    preview = client.post(
        "/employees/import/preview",
        files={
            "file": (
                "employees.csv",
                b"employee_code,first_name,last_name,email\n"
                b"EMP003,New,Employee,new@example.com\n",
                "text/csv",
            )
        },
    )
    assert preview.status_code == 200
    assert preview.json()["valid_rows"] == 1
    with Session(engine) as db:
        assert db.query(Employee).count() == 2


def test_hr_can_hire_employee_with_manager_and_designation(employee_api):
    client, engine, _ = employee_api
    with Session(engine) as db:
        manager = add_employee(db, "MGR001")
        designation = Designation(name="Engineer", is_active=True)
        db.add(designation)
        db.commit()
        manager_id = manager.id
        designation_id = designation.id

    created = client.post(
        "/employees/",
        json={
            "employee_code": "EMP001",
            "first_name": "Amina",
            "last_name": "Khan",
            "email": "amina@example.com",
            "password": "EmployeePass123",
            "reporting_manager_id": manager_id,
            "designation_id": designation_id,
        },
    )

    assert created.status_code == 201
    assert created.json()["reporting_manager_id"] == manager_id
    assert created.json()["designation_id"] == designation_id


def test_employee_document_and_soft_exit_api(employee_api):
    client, engine, _ = employee_api
    with Session(engine) as db:
        employee = add_employee(db, "EMP001")
        employee_id = employee.id
        db.commit()

    uploaded = client.post(
        f"/employees/{employee_id}/documents",
        files={"file": ("offer.pdf", b"%PDF-1.7\noffer", "application/pdf")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]

    listed = client.get(f"/employees/{employee_id}/documents")
    assert listed.status_code == 200
    assert listed.json()[0]["file_name"] == "offer.pdf"

    downloaded = client.get(f"/employees/documents/{document_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.7\noffer"

    exited = client.post(
        f"/employees/{employee_id}/exit",
        json={"exit_date": "2026-10-30", "exit_reason": "Resigned"},
    )
    assert exited.status_code == 200
    assert exited.json()["is_active"] is False
    assert exited.json()["exit_date"] == "2026-10-30"
    assert exited.json()["status"] == "Exited"


def test_manager_employee_api_is_limited_to_direct_reports(employee_api):
    client, engine, test_user = employee_api
    with Session(engine) as db:
        global_read = (
            db.query(Permission)
            .filter(Permission.name == "employee:read:all")
            .one()
        )
        db.query(RolePermission).filter(
            RolePermission.role_id == test_user.role_id,
            RolePermission.permission_id == global_read.id,
        ).delete()
        team_read = Permission(name="employee:team:read")
        db.add(team_read)
        db.flush()
        db.add(
            RolePermission(
                role_id=test_user.role_id,
                permission_id=team_read.id,
            )
        )
        manager = add_employee(db, "MGR001")
        report = add_employee(
            db,
            "EMP001",
            reporting_manager_id=manager.id,
        )
        add_employee(db, "EMP002")
        db.commit()
        manager_id = manager.id
        report_id = report.id
        unrelated_id = db.query(Employee.id).filter(Employee.employee_code == "EMP002").scalar()

    test_user.id = manager_id
    test_user.role.name = "Manager"
    response = client.get("/employees/")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [report_id]
    assert client.get(f"/employees/{report_id}").status_code == 200
    assert client.get(f"/employees/{unrelated_id}").status_code == 404
    assert (
        client.get(
            "/employees/",
            params={"reporting_manager_id": unrelated_id},
        ).status_code
        == 403
    )


def test_designation_management_api(employee_api):
    client, _, _ = employee_api
    created = client.post(
        "/designations/",
        json={"name": "Senior Engineer", "description": "Engineering role"},
    )

    assert created.status_code == 201
    designation_id = created.json()["id"]
    assert client.get("/designations/").json()[0]["name"] == "Senior Engineer"

    updated = client.patch(
        f"/designations/{designation_id}",
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert client.get("/designations/").json() == []
