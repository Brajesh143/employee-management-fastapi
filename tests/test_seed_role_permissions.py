from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.database import Base
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from schemas.role import RoleCreate, RoleResponse, RoleUpdate
from seed.permissions import seed_permissions
from seed.role_permissions import seed_role_permissions
from seed.roles import DEFAULT_ROLES, seed_roles


def test_hr_role_name_is_valid_for_role_requests_and_responses():
    assert RoleCreate(name="HR").name == "HR"
    assert RoleUpdate(name="HR").name == "HR"


def test_seed_roles_and_permissions_creates_catalog_and_preserves_custom_roles():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        seed_roles(db)
        seed_permissions(db)
        seed_role_permissions(db)

        hr_role = db.query(Role).filter(Role.name == "HR").one()
        assert RoleResponse.model_validate(hr_role).name == "HR"

        assert {
            role.name for role in db.query(Role).all()
        } >= {role["name"] for role in DEFAULT_ROLES}

        def permissions_for(role_name: str) -> set[str]:
            return {
                permission_name
                for (permission_name,) in (
                    db.query(Permission.name)
                    .join(
                        RolePermission,
                        Permission.id == RolePermission.permission_id,
                    )
                    .join(Role, Role.id == RolePermission.role_id)
                    .filter(Role.name == role_name)
                    .all()
                )
            }

        all_permission_names = {
            name for (name,) in db.query(Permission.name).all()
        }
        assert permissions_for("Super Admin") == all_permission_names
        assert "employee:read:all" in permissions_for("HR")
        assert "employee:team:read" in permissions_for("Manager")
        assert "attendance:manage" not in permissions_for("Employee")
        assert "role:assign" in permissions_for("Admin")
        assert "recruitment:manage" in permissions_for("HR")
        assert "expense:approve" in permissions_for("HR")
        assert "performance:review" in permissions_for("Manager")
        assert "report:team:read" in permissions_for("Manager")
        assert "payroll:generate" in permissions_for("Finance")
        assert "reimbursement:approve" in permissions_for("Finance")
        assert "payslip:read" in permissions_for("Employee")
        assert "salary:read" not in permissions_for("Employee")
        assert "recruitment:manage" in permissions_for("Recruiter")

        custom_role = Role(name="Custom", description="User-defined role")
        custom_permission = Permission(
            name="custom:read",
            description="Custom permission",
        )
        db.add_all([custom_role, custom_permission])
        db.flush()
        db.add(
            RolePermission(
                role_id=custom_role.id,
                permission_id=custom_permission.id,
            )
        )
        db.commit()

        seed_roles(db)
        seed_permissions(db)
        seed_role_permissions(db)

        assert db.query(Role).filter(Role.name == "HR").count() == 1
        assert (
            db.query(RolePermission)
            .filter(
                RolePermission.role_id == custom_role.id,
                RolePermission.permission_id == custom_permission.id,
            )
            .count()
            == 1
        )
