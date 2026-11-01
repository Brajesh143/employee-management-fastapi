from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from database import get_db
from auth.dependencies import get_current_user

from models.employee import Employee
from models.role_permission import RolePermission
from models.permission import Permission
from models.role import Role

SELF_SERVICE_PERMISSIONS = {
    "ai:chat",
    "attendance:create",
    "attendance:read",
    "leave:create",
    "leave:read",
    "leave:cancel",
    "payslip:read",
    "performance:read",
    "performance:goal:update",
}
ADMIN_DELEGABLE_PERMISSIONS = {
    "employee:team:read",
    "performance:review",
    "performance:read",
    "performance:goal:manage",
    "report:team:read",
}


def get_role_permissions(db: Session, role_id: int | None) -> set[str]:
    if role_id is None:
        return set()

    rows = (
        db.query(Permission.name)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    return {name for (name,) in rows}


def has_permission(db: Session, user: Employee, permission_name: str) -> bool:
    permissions = get_role_permissions(db, user.role_id)
    return "*" in permissions or permission_name in permissions


def require_any_permission(*permission_names: str):
    if not permission_names:
        raise ValueError("At least one permission is required.")

    def permission_checker(
        current_user: Employee = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if current_user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role not assigned.",
            )

        granted_permissions = get_role_permissions(db, current_user.role_id)
        if (
            "*" not in granted_permissions
            and not granted_permissions.intersection(permission_names)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to perform this action.",
            )

        return current_user

    return permission_checker


def require_permission(permission_name: str):
    return require_any_permission(permission_name)


def ensure_role_assignment_allowed(
    db: Session,
    actor: Employee,
    role_id: int | None,
) -> None:
    if role_id is None:
        return

    target_role = db.query(Role).filter(Role.id == role_id).first()
    if target_role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role not found.",
        )

    actor_permissions = get_role_permissions(db, actor.role_id)
    target_permissions = get_role_permissions(db, target_role.id)
    if "*" in actor_permissions:
        return

    actor_role_name = getattr(actor.role, "name", None)
    if (
        has_permission(db, actor, "role:assign")
        and target_role.name != "Super Admin"
        and (
            target_permissions - actor_permissions
        ).issubset(SELF_SERVICE_PERMISSIONS | ADMIN_DELEGABLE_PERMISSIONS)
    ):
        return

    assignable_self_service_permissions = (
        target_permissions - SELF_SERVICE_PERMISSIONS
    )
    if (
        target_role.name == "Employee"
        and actor_role_name in {"HR", "Human Resource"}
        and assignable_self_service_permissions.issubset(actor_permissions)
    ):
        return

    if "*" in target_permissions or not target_permissions.issubset(actor_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot assign a role with permissions you do not have.",
        )


def employee_scope_query(
    db: Session,
    user: Employee,
    query: Query,
    employee_id_column,
) -> Query:
    if has_permission(db, user, "employee:read:all"):
        return query

    if has_permission(db, user, "employee:team:read"):
        accessible_employee_ids = db.query(Employee.id).filter(
            or_(
                Employee.id == user.id,
                Employee.reporting_manager_id == user.id,
            )
        )
    else:
        accessible_employee_ids = [user.id]

    return query.filter(employee_id_column.in_(accessible_employee_ids))


def can_access_employee(
    db: Session,
    user: Employee,
    employee_id: int,
    *,
    include_self: bool = True,
) -> bool:
    if has_permission(db, user, "employee:read:all"):
        return True
    if include_self and employee_id == user.id:
        return True
    if not has_permission(db, user, "employee:team:read"):
        return False

    return (
        db.query(Employee.id)
        .filter(
            Employee.id == employee_id,
            Employee.reporting_manager_id == user.id,
        )
        .first()
        is not None
    )