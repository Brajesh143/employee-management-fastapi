from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import main  # noqa: F401
from database.database import Base
from models.attendence import Attendance
from models.audit_log import AuditLog
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.salary import Salary
from models.salary_structure import SalaryStructure
from seed.reset_and_seed import (
    SUPER_ADMIN_EMAIL,
    reset_and_seed_super_admin,
)
from seed.roles import DEFAULT_ROLES


def test_reset_reseeds_roles_and_creates_one_super_admin():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        old_role = Role(name="Old Role", description="Removed by reset")
        old_permission = Permission(
            name="old:read",
            description="Removed mapping by reset",
        )
        db.add_all([old_role, old_permission])
        db.flush()
        employee = Employee(
            employee_code="OLD001",
            first_name="Old",
            last_name="Employee",
            email="old@example.com",
            password_hash="old-password-hash",
            role_id=old_role.id,
            token_version=2,
            joining_date=date(2025, 1, 1),
            is_active=True,
        )
        db.add(employee)
        db.flush()
        old_permission_id = old_permission.id
        db.add_all(
            [
                Salary(
                    employee_id=employee.id,
                    month=1,
                    year=2025,
                    basic_salary=1000,
                    net_salary=1000,
                ),
                SalaryStructure(
                    employee_id=employee.id,
                    basic_salary=1000,
                    effective_from=date(2025, 1, 1),
                ),
                Attendance(
                    employee_id=employee.id,
                    attendance_date=date(2025, 1, 2),
                    check_in=datetime(2025, 1, 2, 9),
                ),
                AuditLog(
                    actor_id=employee.id,
                    action="test",
                    resource_type="employee",
                ),
                RolePermission(
                    role_id=old_role.id,
                    permission_id=old_permission.id,
                ),
            ]
        )
        db.commit()

        stored_keys = reset_and_seed_super_admin(
            db,
            "a-private-super-admin-password",
        )

        employees = db.query(Employee).all()
        assert len(employees) == 1
        assert employees[0].email == SUPER_ADMIN_EMAIL
        assert employees[0].role.name == "Super Admin"
        assert employees[0].token_version == 3
        assert employees[0].password_hash != "a-private-super-admin-password"
        assert db.query(Salary).count() == 0
        assert db.query(SalaryStructure).count() == 0
        assert db.query(Attendance).count() == 0
        assert db.query(Role).filter(Role.name == "Old Role").count() == 0
        assert {
            role.name for role in db.query(Role).all()
        } == {role["name"] for role in DEFAULT_ROLES}
        assert (
            db.query(RolePermission)
            .join(Role)
            .filter(
                Role.name != "Super Admin",
                RolePermission.permission_id == old_permission_id,
            )
            .count()
            == 0
        )
        assert db.query(AuditLog).one().actor_id is None
        assert stored_keys == []

        super_admin_role = db.query(Role).filter_by(name="Super Admin").one()
        all_permission_ids = {
            permission.id for permission in db.query(Permission).all()
        }
        assigned_permission_ids = {
            permission_id
            for (permission_id,) in (
                db.query(RolePermission.permission_id)
                .filter(RolePermission.role_id == super_admin_role.id)
                .all()
            )
        }
        assert assigned_permission_ids == all_permission_ids

    engine.dispose()


def test_reset_rejects_passwords_outside_supported_limits():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        with pytest.raises(ValueError, match="at least 8 characters"):
            reset_and_seed_super_admin(db, "short")

    engine.dispose()
