import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from crud.permission import (
    create_permission,
    delete_permission,
    list_role_permissions,
    replace_role_permissions,
    update_permission,
)
from database.database import Base
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from schemas.permission import PermissionCreate, PermissionUpdate


@pytest.fixture
def permission_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _role(db: Session, name: str, *permission_names: str) -> Role:
    role = Role(name=name)
    db.add(role)
    for permission_name in permission_names:
        permission = (
            db.query(Permission)
            .filter(Permission.name == permission_name)
            .first()
        )
        if permission is None:
            permission = Permission(name=permission_name)
            db.add(permission)
            db.flush()
        db.add(RolePermission(role=role, permission=permission))
    db.flush()
    return role


def _employee(db: Session, role: Role) -> Employee:
    employee = Employee(
        employee_code="SUPER001",
        first_name="Super",
        last_name="Admin",
        email="super-admin@example.com",
        password_hash="",
        role=role,
    )
    db.add(employee)
    db.flush()
    return employee


def test_permission_catalog_crud_normalizes_and_protects_assigned_rows(
    permission_db: Session,
):
    super_admin_role = _role(permission_db, "Super Admin")
    permission = create_permission(
        permission_db,
        PermissionCreate(name="  Employee:Cost_Center:Read  "),
    )
    assert permission.name == "employee:cost_center:read"
    assert permission in list_role_permissions(permission_db, super_admin_role.id)

    updated = update_permission(
        permission_db,
        permission.id,
        PermissionUpdate(description="Read cost center"),
    )
    assert updated is not None
    assert updated.description == "Read cost center"

    role = _role(permission_db, "Custom", permission.name)
    with pytest.raises(HTTPException) as error:
        delete_permission(permission_db, permission.id)
    assert error.value.status_code == 409
    assert list_role_permissions(permission_db, role.id) == [permission]

    unassigned = create_permission(
        permission_db,
        PermissionCreate(name="temporary:read"),
    )
    assert delete_permission(permission_db, unassigned.id) == unassigned


def test_role_permission_replacement_rejects_ungranted_privileges(
    permission_db: Session,
):
    admin_role = _role(permission_db, "Admin", "role:assign", "employee:read")
    target_role = _role(permission_db, "Custom")
    secret_permission = Permission(name="secrets:manage")
    permission_db.add(secret_permission)
    permission_db.flush()
    actor = _employee(permission_db, admin_role)

    with pytest.raises(HTTPException) as error:
        replace_role_permissions(
            permission_db,
            target_role.id,
            [secret_permission.id],
            actor,
        )
    assert error.value.status_code == 403


def test_super_admin_can_replace_role_permissions_and_unknown_ids_fail(
    permission_db: Session,
):
    super_admin_role = _role(permission_db, "Super Admin", "*")
    target_role = _role(permission_db, "Manager")
    team_permission = Permission(name="employee:team:read")
    permission_db.add(team_permission)
    permission_db.flush()
    actor = _employee(permission_db, super_admin_role)

    assigned = replace_role_permissions(
        permission_db,
        target_role.id,
        [team_permission.id],
        actor,
    )
    assert assigned == [team_permission]
    assert list_role_permissions(permission_db, target_role.id) == [team_permission]

    with pytest.raises(HTTPException) as error:
        replace_role_permissions(permission_db, target_role.id, [9999], actor)
    assert error.value.status_code == 422


def test_super_admin_permissions_cannot_be_removed(
    permission_db: Session,
):
    super_admin_role = _role(permission_db, "Super Admin", "role:assign")
    actor = _employee(permission_db, super_admin_role)

    with pytest.raises(HTTPException) as error:
        replace_role_permissions(permission_db, super_admin_role.id, [], actor)
    assert error.value.status_code == 409


def test_permission_names_reject_invalid_parts():
    with pytest.raises(ValueError):
        PermissionCreate(name="employee::read")
