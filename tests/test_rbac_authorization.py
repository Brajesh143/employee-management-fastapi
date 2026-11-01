import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import main  # noqa: F401
from auth.permissions import (
    can_access_employee,
    employee_scope_query,
    ensure_role_assignment_allowed,
    has_permission,
    require_permission,
)
from crud.role import delete_role, update_role
from database.database import Base
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.permission import router as permission_router
from schemas.role import RoleUpdate


@pytest.fixture
def rbac_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _create_role(db: Session, name: str, *permission_names: str) -> Role:
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
        db.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id,
            )
        )
    db.flush()
    return role


def _create_employee(db: Session, code: str, role: Role, **kwargs) -> Employee:
    employee = Employee(
        employee_code=code,
        first_name=code,
        last_name="Test",
        email=f"{code.lower()}@example.com",
        password_hash="",
        role=role,
        **kwargs,
    )
    db.add(employee)
    db.flush()
    return employee


def test_role_assignment_cannot_grant_permissions_actor_does_not_have(
    rbac_db: Session,
):
    hr_role = _create_role(
        rbac_db,
        "HR",
        "employee:create",
        "employee:update",
        "attendance:read",
    )
    employee_role = _create_role(
        rbac_db,
        "Employee",
        "attendance:read",
        "ai:chat",
    )
    admin_role = _create_role(
        rbac_db,
        "Admin",
        "employee:create",
        "employee:update",
        "role:delete",
    )
    actor = _create_employee(rbac_db, "HR001", hr_role)

    ensure_role_assignment_allowed(rbac_db, actor, employee_role.id)
    with pytest.raises(HTTPException) as error:
        ensure_role_assignment_allowed(rbac_db, actor, admin_role.id)
    assert error.value.status_code == 403

    privileged_permission = Permission(name="system:config")
    rbac_db.add(privileged_permission)
    rbac_db.flush()
    rbac_db.add(
        RolePermission(
            role_id=employee_role.id,
            permission_id=privileged_permission.id,
        )
    )
    rbac_db.flush()
    with pytest.raises(HTTPException) as privileged_error:
        ensure_role_assignment_allowed(rbac_db, actor, employee_role.id)
    assert privileged_error.value.status_code == 403


def test_manager_employee_scope_includes_only_self_and_direct_reports(
    rbac_db: Session,
):
    manager_role = _create_role(
        rbac_db,
        "Manager",
        "employee:read",
        "employee:team:read",
    )
    employee_role = _create_role(rbac_db, "Employee", "employee:read")
    manager = _create_employee(rbac_db, "MGR001", manager_role)
    report = _create_employee(
        rbac_db,
        "EMP001",
        employee_role,
        reporting_manager_id=manager.id,
    )
    unrelated = _create_employee(rbac_db, "EMP002", employee_role)

    scoped_ids = {
        employee.id
        for employee in employee_scope_query(
            rbac_db,
            manager,
            rbac_db.query(Employee),
            Employee.id,
        ).all()
    }

    assert scoped_ids == {manager.id, report.id}
    assert can_access_employee(rbac_db, manager, report.id)
    assert not can_access_employee(rbac_db, manager, unrelated.id)


def test_admin_can_assign_delegated_manager_role_but_not_super_admin(
    rbac_db: Session,
):
    admin_role = _create_role(
        rbac_db,
        "Admin",
        "employee:create",
        "employee:read",
        "role:assign",
        "attendance:create",
        "attendance:read",
        "attendance:correct",
        "attendance:wfh",
        "leave:read",
        "leave:approve",
        "report:read",
    )
    manager_role = _create_role(
        rbac_db,
        "Manager",
        "employee:read",
        "employee:team:read",
        "attendance:read",
        "report:read",
        "report:team:read",
        "performance:review",
    )
    super_admin_role = _create_role(rbac_db, "Super Admin", "system:config")
    admin = _create_employee(rbac_db, "ADM001", admin_role)

    ensure_role_assignment_allowed(rbac_db, admin, manager_role.id)
    with pytest.raises(HTTPException) as error:
        ensure_role_assignment_allowed(rbac_db, admin, super_admin_role.id)
    assert error.value.status_code == 403


def test_ai_chat_route_requires_ai_chat_permission():
    route = next(
        route
        for route in main.ai_chat.router.routes
        if isinstance(route, APIRoute) and route.path == "/ai/chat"
    )
    dependencies = [
        dependency.call
        for dependency in route.dependant.dependencies
    ]

    assert any(
        getattr(dependency, "__name__", "") == "permission_checker"
        for dependency in dependencies
    )


def test_role_wildcard_grants_all_permissions(rbac_db: Session):
    admin_role = _create_role(rbac_db, "Super Admin", "*")
    employee = _create_employee(rbac_db, "SA001", admin_role)

    assert has_permission(rbac_db, employee, "ai:chat")
    assert has_permission(rbac_db, employee, "system:config")


def test_permission_catalog_allows_permission_managers_and_role_assigners(
    rbac_db: Session,
):
    route = next(
        route
        for route in permission_router.routes
        if isinstance(route, APIRoute)
        and route.path == "/"
        and "GET" in route.methods
    )
    checker = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "permission_checker"
    )
    admin_role = _create_role(rbac_db, "Admin", "role:assign")
    employee_role = _create_role(rbac_db, "Employee", "attendance:read")
    admin = _create_employee(rbac_db, "ADM002", admin_role)
    employee = _create_employee(rbac_db, "EMP004", employee_role)

    assert checker(current_user=admin, db=rbac_db) is admin
    with pytest.raises(HTTPException) as error:
        checker(current_user=employee, db=rbac_db)
    assert error.value.status_code == 403


def test_ai_permission_is_checked_and_system_roles_are_protected(
    rbac_db: Session,
):
    employee_role = _create_role(rbac_db, "Employee", "attendance:read")
    employee = _create_employee(rbac_db, "EMP003", employee_role)

    with pytest.raises(HTTPException) as error:
        require_permission("ai:chat")(current_user=employee, db=rbac_db)
    assert error.value.status_code == 403

    with pytest.raises(HTTPException) as rename_error:
        update_role(
            rbac_db,
            employee_role.id,
            RoleUpdate(name="Human Resources"),
        )
    assert rename_error.value.status_code == 409

    with pytest.raises(HTTPException) as delete_error:
        delete_role(rbac_db, employee_role.id)
    assert delete_error.value.status_code == 409


def test_legacy_attendance_creation_requires_manage_permission(
    rbac_db: Session,
):
    employee_role = _create_role(rbac_db, "Employee", "attendance:create")
    employee = _create_employee(rbac_db, "EMP004", employee_role)
    route = next(
        route
        for route in main.attendence.router.routes
        if isinstance(route, APIRoute)
        and "POST" in route.methods
        and route.path == "/"
    )
    permission_checker = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "permission_checker"
    )

    with pytest.raises(HTTPException) as error:
        permission_checker(current_user=employee, db=rbac_db)
    assert error.value.status_code == 403
