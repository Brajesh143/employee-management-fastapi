from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.database import Base
from models.attendence import Attendance
from models.department import Department
from models.employee import Employee
from models.leave import Leave
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.salary import Salary
from seed.permissions import seed_permissions


def test_seed_permissions_creates_default_permissions():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        seed_permissions(db)

        permission = (
            db.query(Permission)
            .filter(Permission.name == "employee:create")
            .first()
        )

        assert permission is not None
        assert permission.description == "Create employee"
