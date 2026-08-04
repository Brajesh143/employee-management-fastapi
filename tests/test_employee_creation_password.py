from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.database import Base
from crud.auth import login_employee
from crud.employee import create_employee
from models.department import Department
from models.leave import Leave
from models.role import Role
from schemas.auth import LoginRequest
from schemas.employee import EmployeeCreate


def test_create_employee_stores_hashed_password_and_null_last_login():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        payload = EmployeeCreate(
            employee_code="EMP999",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            password="secret123",
            phone="1234567890",
            gender="Male",
            department_id=None,
            role_id=None,
            address="Test",
            salary=1000.0,
            is_verified=False,
            profile_image=None,
            status="Active",
            dob=None,
            joining_date=None,
        )

        employee = create_employee(db, payload)

        assert employee.password_hash != ""
        assert employee.password_hash != payload.password
        assert employee.last_login is None


def test_login_accepts_case_insensitive_email():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        payload = EmployeeCreate(
            employee_code="EMP998",
            first_name="Case",
            last_name="Test",
            email="CaseUser@example.com",
            password="secret123",
            phone="1234567890",
            gender="Male",
            department_id=None,
            role_id=None,
            address="Test",
            salary=1000.0,
            is_verified=False,
            profile_image=None,
            status="Active",
            dob=None,
            joining_date=None,
        )

        create_employee(db, payload)

        result = login_employee(
            db,
            LoginRequest(email="caseuser@example.com", password="secret123"),
        )

        assert result["access_token"]
