from sqlalchemy.orm import Session

from models.department import Department  # noqa: F401
from models.employee import Employee  # noqa: F401
from models.leave import Leave  # noqa: F401
from models.permission import Permission
from models.role import Role  # noqa: F401
from models.role_permission import RolePermission  # noqa: F401


DEFAULT_PERMISSIONS = [
    # Employee
    {
        "name": "employee:create",
        "description": "Create employee"
    },
    {
        "name": "employee:read",
        "description": "View employee"
    },
    {
        "name": "employee:update",
        "description": "Update employee"
    },
    {
        "name": "employee:delete",
        "description": "Delete employee"
    },

    # Department
    {
        "name": "department:create",
        "description": "Create department"
    },
    {
        "name": "department:read",
        "description": "View department"
    },
    {
        "name": "department:update",
        "description": "Update department"
    },
    {
        "name": "department:delete",
        "description": "Delete department"
    },

    # Role
    {
        "name": "role:create",
        "description": "Create role"
    },
    {
        "name": "role:read",
        "description": "View role"
    },
    {
        "name": "role:update",
        "description": "Update role"
    },
    {
        "name": "role:delete",
        "description": "Delete role"
    },

    # Attendance
    {
        "name": "attendance:create",
        "description": "Mark attendance"
    },
    {
        "name": "attendance:read",
        "description": "View attendance"
    },
    {
        "name": "attendance:update",
        "description": "Update attendance"
    },
    {
        "name": "attendance:delete",
        "description": "Delete attendance"
    },

    # Leave
    {
        "name": "leave:create",
        "description": "Apply leave"
    },
    {
        "name": "leave:read",
        "description": "View leave"
    },
    {
        "name": "leave:update",
        "description": "Update leave"
    },
    {
        "name": "leave:delete",
        "description": "Delete leave"
    },
    {
        "name": "leave:approve",
        "description": "Approve leave"
    },

    # Salary
    {
        "name": "salary:create",
        "description": "Create salary"
    },
    {
        "name": "salary:read",
        "description": "View salary"
    },
    {
        "name": "salary:update",
        "description": "Update salary"
    },
    {
        "name": "salary:delete",
        "description": "Delete salary"
    }
]


def seed_permissions(db: Session):

    for permission in DEFAULT_PERMISSIONS:

        exists = (
            db.query(Permission)
            .filter(Permission.name == permission["name"])
            .first()
        )

        if not exists:
            db.add(Permission(**permission))

    db.commit()

    print("Permissions seeded successfully.")