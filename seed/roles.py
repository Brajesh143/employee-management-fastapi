from sqlalchemy.orm import Session

from models.department import Department  # noqa: F401
from models.employee import Employee  # noqa: F401
from models.leave import Leave  # noqa: F401
from models.permission import Permission  # noqa: F401
from models.role import Role
from models.role_permission import RolePermission  # noqa: F401
from models.shift import Shift  # noqa: F401


DEFAULT_ROLES = [
    {
        "name": "Super Admin",
        "description": "Full access to all application permissions and system administration.",
    },
    {
        "name": "Admin",
        "description": "Organization setup, employee administration, payroll operations, and reports.",
    },
    {
        "name": "HR",
        "description": "Employee administration, attendance corrections, leave, recruitment, and expenses.",
    },
    {
        "name": "Manager",
        "description": "Team attendance and leave approvals, performance reviews, and team reports.",
    },
    {
        "name": "Finance",
        "description": "Payroll, expenses, reimbursements, and payroll reports.",
    },
    {
        "name": "Employee",
        "description": "Self-service attendance, leave, payslip, and AI chat.",
    },
    {
        "name": "Recruiter",
        "description": "Job openings, candidate management, and interviews.",
    },
]


def seed_roles(db: Session) -> None:
    try:
        existing_names = {name for (name,) in db.query(Role.name).all()}
        for role_data in DEFAULT_ROLES:
            if role_data["name"] not in existing_names:
                db.add(Role(**role_data))

        db.commit()
        print("Roles seeded successfully.")
    except Exception:
        db.rollback()
        raise
