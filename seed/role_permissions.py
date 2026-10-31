from sqlalchemy.orm import Session

from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission


ROLE_PERMISSIONS = {
    "Super Admin": [
        "*"
    ],

    "Admin": [
        "employee:create",
        "employee:read",
        "employee:read:all",
        "employee:update",
        "employee:delete",
        "employee:import",
        "employee:export",
        "document:manage",

        "department:create",
        "department:read",
        "department:update",
        "department:delete",

        "role:create",
        "role:read",
        "role:update",
        "role:delete",
        "role:assign",

        "attendance:create",
        "attendance:manage",
        "attendance:read",
        "attendance:update",
        "attendance:delete",
        "attendance:correct",
        "attendance:wfh",

        "leave:create",
        "leave:read",
        "leave:update",
        "leave:delete",
        "leave:approve",
        "leave:cancel",
        "leave:balance:manage",

        "salary:create",
        "salary:read",
        "salary:update",
        "salary:delete",
        "payroll:generate",
        "payslip:read",

        "expense:create",
        "expense:read",
        "expense:update",
        "expense:delete",
        "expense:approve",
        "reimbursement:create",
        "reimbursement:read",
        "reimbursement:approve",

        "report:read",
        "audit:read",
        "notification:manage",
    ],

    "HR": [
        "employee:create",
        "employee:read",
        "employee:read:all",
        "employee:update",
        "employee:import",
        "employee:export",
        "document:manage",

        "department:read",

        "attendance:create",
        "attendance:manage",
        "attendance:read",
        "attendance:update",
        "attendance:correct",
        "attendance:wfh",

        "leave:read",
        "leave:approve",
        "leave:cancel",
        "leave:balance:manage",

        "expense:create",
        "expense:read",
        "expense:update",
        "expense:approve",
        "reimbursement:read",
        "recruitment:manage",

        "report:read",
        "notification:manage",
    ],

    # Retain permissions for installations that already have the former role name.
    "Human Resource": [
        "employee:create",
        "employee:read",
        "employee:read:all",
        "employee:update",
        "employee:import",
        "employee:export",
        "document:manage",
        "department:read",
        "attendance:create",
        "attendance:manage",
        "attendance:read",
        "attendance:update",
        "attendance:correct",
        "attendance:wfh",
        "leave:read",
        "leave:approve",
        "leave:cancel",
        "leave:balance:manage",
        "expense:create",
        "expense:read",
        "expense:update",
        "expense:approve",
        "reimbursement:read",
        "recruitment:manage",
        "report:read",
        "notification:manage",
    ],

    "Manager": [
        "employee:read",
        "employee:team:read",

        "attendance:create",
        "attendance:read",
        "attendance:correct",
        "attendance:wfh",

        "leave:read",
        "leave:approve",

        "report:read",
        "report:team:read",
        "performance:review",
    ],

    "Finance": [
        "salary:create",
        "salary:read",
        "salary:update",
        "salary:delete",
        "payroll:generate",
        "payslip:read",
        "expense:create",
        "expense:read",
        "expense:update",
        "expense:delete",
        "expense:approve",
        "reimbursement:create",
        "reimbursement:read",
        "reimbursement:approve",
        "report:read",
    ],

    "Employee": [
        "attendance:create",
        "attendance:read",

        "leave:create",
        "leave:read",
        "leave:cancel",
        "payslip:read",
        "ai:chat",
    ],

    "Recruiter": [
        "recruitment:manage",
    ],
}


def seed_role_permissions(db: Session) -> None:

    try:
        all_permissions = {
            permission.name: permission
            for permission in db.query(Permission).all()
        }
        missing_permissions = sorted(
            {
                permission_name
                for permission_names in ROLE_PERMISSIONS.values()
                for permission_name in permission_names
                if permission_name != "*" and permission_name not in all_permissions
            }
        )
        if missing_permissions:
            raise ValueError(
                "Role permission seed references undefined permissions: "
                + ", ".join(missing_permissions)
            )

        roles = {
            role.name: role
            for role in db.query(Role)
            .filter(Role.name.in_(ROLE_PERMISSIONS))
            .all()
        }

        if roles:
            role_ids = [role.id for role in roles.values()]
            db.query(RolePermission).filter(
                RolePermission.role_id.in_(role_ids)
            ).delete(synchronize_session=False)

        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = roles.get(role_name)
            if role is None:
                continue

            if "*" in permission_names:
                permissions = all_permissions.values()
            else:
                permissions = [
                    all_permissions[name] for name in permission_names
                ]

            for permission in permissions:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )

        db.commit()

        print("Role permissions seeded successfully.")

    except Exception:
        db.rollback()
        raise