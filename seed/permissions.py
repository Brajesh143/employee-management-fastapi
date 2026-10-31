from sqlalchemy.orm import Session

from models.department import Department  # noqa: F401
from models.designation import Designation  # noqa: F401
from models.employee import Employee  # noqa: F401
from models.employee_document import EmployeeDocument  # noqa: F401
from models.leave import Leave  # noqa: F401
from models.permission import Permission
from models.role import Role  # noqa: F401
from models.role_permission import RolePermission  # noqa: F401
from models.shift import Shift  # noqa: F401


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
        "name": "employee:read:all",
        "description": "View employee records across the organization"
    },
    {
        "name": "employee:team:read",
        "description": "View employee records for direct reports"
    },
    {
        "name": "employee:update",
        "description": "Update employee"
    },
    {
        "name": "employee:delete",
        "description": "Delete employee"
    },
    {
        "name": "employee:import",
        "description": "Import employees"
    },
    {
        "name": "employee:export",
        "description": "Export employees"
    },

    # Documents
    {
        "name": "document:manage",
        "description": "Manage employee documents"
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
    {
        "name": "role:assign",
        "description": "Assign roles with delegated permissions to employees"
    },
    {
        "name": "permission:manage",
        "description": "Create, update, and delete permission definitions"
    },

    # Attendance
    {
        "name": "attendance:create",
        "description": "Mark attendance"
    },
    {
        "name": "attendance:manage",
        "description": "Create or manage attendance records outside self-service check-in"
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
    {
        "name": "attendance:correct",
        "description": "Approve or reject attendance corrections"
    },
    {
        "name": "attendance:wfh",
        "description": "Approve or reject work-from-home requests"
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
    {
        "name": "leave:cancel",
        "description": "Cancel leave requests"
    },
    {
        "name": "leave:balance:manage",
        "description": "Manage employee leave balances"
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
    },
    {
        "name": "payroll:generate",
        "description": "Generate payroll"
    },
    {
        "name": "payslip:read",
        "description": "View payslips"
    },

    # Expenses and reimbursements
    {
        "name": "expense:create",
        "description": "Create expense claims"
    },
    {
        "name": "expense:read",
        "description": "View expense claims"
    },
    {
        "name": "expense:update",
        "description": "Update expense claims"
    },
    {
        "name": "expense:delete",
        "description": "Delete expense claims"
    },
    {
        "name": "expense:approve",
        "description": "Approve expense claims"
    },
    {
        "name": "reimbursement:create",
        "description": "Create reimbursement requests"
    },
    {
        "name": "reimbursement:read",
        "description": "View reimbursement requests"
    },
    {
        "name": "reimbursement:approve",
        "description": "Approve reimbursement requests"
    },

    # Performance and recruitment
    {
        "name": "performance:review",
        "description": "Create and manage performance reviews"
    },
    {
        "name": "recruitment:manage",
        "description": "Manage job openings, candidates, and interviews"
    },

    # Reports
    {
        "name": "report:read",
        "description": "View attendance and HR reports"
    },
    {
        "name": "report:team:read",
        "description": "View team reports"
    },

    # AI, audit, notifications, and system administration
    {
        "name": "ai:chat",
        "description": "Use self-service AI chat"
    },
    {
        "name": "ai:admin",
        "description": "Administer AI features and configuration"
    },
    {
        "name": "audit:read",
        "description": "View audit logs"
    },
    {
        "name": "notification:manage",
        "description": "Manage application notifications"
    },
    {
        "name": "system:config",
        "description": "Manage system configuration"
    },
    {
        "name": "secrets:manage",
        "description": "Manage application secrets"
    },
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