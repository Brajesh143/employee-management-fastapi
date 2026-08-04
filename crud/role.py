from sqlalchemy.orm import Session
from models.role import Role
from schemas.role import RoleCreate, RoleUpdate

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

    # db_role.name = role.name
    # db_role.description = role.description

    update_data = role.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_role, key, value)


    db.commit()
    db.refresh(db_role)

    return db_role

def delete_role(db: Session, role_id: int):

    db_role = get_role(db, role_id)

    if not db_role:
        return None

    db.delete(db_role)
    db.commit()

    return db_role
