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
        "employee:update",
        "employee:delete",

        "department:create",
        "department:read",
        "department:update",
        "department:delete",

        "role:create",
        "role:read",
        "role:update",
        "role:delete",

        "attendance:create",
        "attendance:read",
        "attendance:update",
        "attendance:delete",

        "leave:create",
        "leave:read",
        "leave:update",
        "leave:delete",
        "leave:approve",

        "salary:create",
        "salary:read",
        "salary:update",
        "salary:delete",
    ],

    "Human Resource": [
        "employee:create",
        "employee:read",
        "employee:update",

        "department:read",

        "attendance:create",
        "attendance:read",
        "attendance:update",

        "leave:read",
        "leave:approve",

        "salary:read",
    ],

    "Manager": [
        "employee:read",

        "attendance:read",

        "leave:read",
        "leave:approve",

        "salary:read",
    ],

    "Employee": [
        "attendance:read",

        "leave:create",
        "leave:read",

        "salary:read",
    ],
}

def seed_role_permissions(db: Session):

    try:
        db.query(RolePermission).delete(
            synchronize_session=False
        )

        all_permissions = {
            permission.name: permission
            for permission in db.query(Permission).all()
        }

        for role_name, permission_names in ROLE_PERMISSIONS.items():

            role = (
                db.query(Role)
                .filter(Role.name == role_name)
                .first()
            )

            if role is None:
                print(f"Role '{role_name}' not found.")
                continue

            if "*" in permission_names:
                permissions = all_permissions.values()
            else:
                permissions = [
                    all_permissions[name]
                    for name in permission_names
                    if name in all_permissions
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