from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.permissions import (
    ADMIN_DELEGABLE_PERMISSIONS,
    SELF_SERVICE_PERMISSIONS,
    get_role_permissions,
)
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from schemas.permission import PermissionCreate, PermissionUpdate


def list_permissions(db: Session) -> list[Permission]:
    return db.query(Permission).order_by(Permission.name).all()


def get_permission(db: Session, permission_id: int) -> Permission | None:
    return db.query(Permission).filter(Permission.id == permission_id).first()


def create_permission(db: Session, payload: PermissionCreate) -> Permission:
    permission = Permission(
        name=payload.name,
        description=payload.description,
    )
    db.add(permission)
    try:
        db.flush()
        super_admin_roles = (
            db.query(Role)
            .filter(Role.name == "Super Admin")
            .all()
        )
        db.add_all(
            [
                RolePermission(role_id=role.id, permission_id=permission.id)
                for role in super_admin_roles
            ]
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A permission with this name already exists.",
        ) from error
    db.refresh(permission)
    return permission


def update_permission(
    db: Session,
    permission_id: int,
    payload: PermissionUpdate,
) -> Permission | None:
    permission = get_permission(db, permission_id)
    if permission is None:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(permission, field, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A permission with this name already exists.",
        ) from error
    db.refresh(permission)
    return permission


def delete_permission(db: Session, permission_id: int) -> Permission | None:
    permission = get_permission(db, permission_id)
    if permission is None:
        return None
    non_super_admin_assignment = (
        db.query(RolePermission)
        .join(Role, Role.id == RolePermission.role_id)
        .filter(
            RolePermission.permission_id == permission_id,
            Role.name != "Super Admin",
        )
        .first()
    )
    if non_super_admin_assignment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission is assigned to one or more roles and cannot be deleted.",
        )

    db.query(RolePermission).filter(
        RolePermission.permission_id == permission_id
    ).delete(synchronize_session=False)
    db.delete(permission)
    db.commit()
    return permission


def list_role_permissions(db: Session, role_id: int) -> list[Permission] | None:
    role = db.query(Role).filter(Role.id == role_id).first()
    if role is None:
        return None
    return (
        db.query(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id == role_id)
        .order_by(Permission.name)
        .all()
    )


def _validate_role_permissions(
    db: Session,
    actor: Employee,
    role: Role,
    requested_permissions: set[str],
) -> None:
    actor_permissions = get_role_permissions(db, actor.role_id)
    if "*" in actor_permissions:
        return

    if role.name == "Super Admin" or "*" in requested_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Super Admin may grant Super Admin permissions.",
        )

    if (
        role.name == "Employee"
        and getattr(actor.role, "name", None) in {"HR", "Human Resource"}
        and (requested_permissions - SELF_SERVICE_PERMISSIONS).issubset(actor_permissions)
    ):
        return

    allowed_delegation = (
        actor_permissions | ADMIN_DELEGABLE_PERMISSIONS | SELF_SERVICE_PERMISSIONS
    )
    if not requested_permissions.issubset(allowed_delegation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot grant permissions you do not have.",
        )


def replace_role_permissions(
    db: Session,
    role_id: int,
    permission_ids: list[int],
    actor: Employee,
) -> list[Permission] | None:
    role = db.query(Role).filter(Role.id == role_id).first()
    if role is None:
        return None
    if role.name == "Super Admin":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Super Admin always has all permissions and cannot be modified.",
        )

    unique_ids = set(permission_ids)
    permissions = (
        db.query(Permission)
        .filter(Permission.id.in_(unique_ids))
        .all()
        if unique_ids
        else []
    )
    if len(permissions) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more permission IDs do not exist.",
        )

    _validate_role_permissions(
        db,
        actor,
        role,
        {permission.name for permission in permissions},
    )

    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(
        synchronize_session=False
    )
    db.add_all(
        [
            RolePermission(role_id=role_id, permission_id=permission.id)
            for permission in permissions
        ]
    )
    db.commit()
    return sorted(permissions, key=lambda permission: permission.name)
