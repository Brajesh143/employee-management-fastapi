from sqlalchemy.orm import Session
from models.leave import Leave
from schemas.leave import LeaveCreate, LeaveUpdate

def create_leave(db: Session, leave: LeaveCreate):
    db_leave = Leave(
        employee_id=leave.employee_id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        total_days=leave.total_days,
        reason=leave.reason,
        status=leave.status,
        approved_by=leave.approved_by,
        approved_at=leave.approved_at
    )
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)

    return db_leave

def get_leaves(db: Session):
    return db.query(Leave).all()

def get_leave(db: Session, leave_id: int):
    return db.query(Leave).filter(Leave.id == leave_id).first()

def update_leave(db: Session, leave_id: int, leave: LeaveUpdate):
    db_leave = get_leave(db, leave_id)

    if not db_leave:
        return None

    update_data = leave.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_leave, key, value)

    db.commit()
    db.refresh(db_leave)

    return db_leave

def delete_leave(db: Session, leave_id: int):
    db_leave = get_leave(db, leave_id)

    if not db_leave:
        return None

    db.delete(db_leave)
    db.commit()

    return db_leave
