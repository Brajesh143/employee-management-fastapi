from sqlalchemy.orm import Session
from models.leave import Leave
from schemas.leave import LeaveCreate, LeaveUpdate

def create_leave(db: Session, leave: LeaveCreate):
    print("=====", leave)
    db_leave = Leave(
        employee_id=leave.employee_id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        total_days=calculate_total_days(leave.start_date, leave.end_date),
        reason=leave.reason,
        status='Pending',
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

def get_my_leaves(db: Session, employee_id: int):
    return db.query(Leave).filter(Leave.employee_id == employee_id).all()

def calculate_total_days(start_date, end_date):
    if not start_date or not end_date:
        return 0

    return (end_date - start_date).days + 1