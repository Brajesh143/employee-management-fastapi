from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models.employee import Employee
from models.role import Role
from schemas.role import RoleCreate, RoleUpdate

SYSTEM_ROLE_NAMES = {
    "Super Admin",
    "Admin",
    "HR",
    "Human Resource",
    "Manager",
    "Finance",
    "Employee",
    "Recruiter",
}


def create_role(db: Session, role: RoleCreate):

    db_role = Role(
        name=role.name,
        description=role.description
    )

    db.add(db_role)
    db.commit()
    db.refresh(db_role)

    return db_role

def get_roles(db: Session):

    return db.query(Role).all()

def get_role(db: Session, role_id: int):

    return (
        db.query(Role)
        .filter(Role.id == role_id)
        .first()
    )

def update_role(db: Session, role_id: int, role: RoleUpdate):

    db_role = get_role(db, role_id)

    if not db_role:
        return None

    update_data = role.model_dump(exclude_unset=True)
    if (
        db_role.name in SYSTEM_ROLE_NAMES
        and update_data.get("name", db_role.name) != db_role.name
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Default system role names cannot be changed.",
        )

    for key, value in update_data.items():
        setattr(db_role, key, value)

    db.commit()
    db.refresh(db_role)

    return db_role

def delete_role(db: Session, role_id: int):

    db_role = get_role(db, role_id)

    if not db_role:
        return None

    if db_role.name in SYSTEM_ROLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Default system roles cannot be deleted.",
        )

    if (
        db.query(Employee.id)
        .filter(Employee.role_id == db_role.id)
        .first()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Roles assigned to employees cannot be deleted.",
        )

    db.delete(db_role)
    db.commit()

    return db_role
