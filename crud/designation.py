from sqlalchemy.orm import Session

from models.designation import Designation
from schemas.designation import DesignationCreate, DesignationUpdate


def get_designations(db: Session) -> list[Designation]:
    return (
        db.query(Designation)
        .filter(Designation.is_active.is_(True))
        .order_by(Designation.name)
        .all()
    )


def create_designation(db: Session, designation: DesignationCreate) -> Designation:
    record = Designation(**designation.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_designation(
    db: Session,
    designation_id: int,
    designation: DesignationUpdate,
) -> Designation | None:
    record = db.query(Designation).filter(Designation.id == designation_id).first()
    if record is None:
        return None

    for key, value in designation.model_dump(exclude_unset=True).items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return record
