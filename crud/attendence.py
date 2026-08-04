from sqlalchemy.orm import Session
from models.attendence import Attendance
from schemas.attendence import AttendanceCreate, AttendanceUpdate

def create_attendance(db: Session, attendance: AttendanceCreate):
    db_attendance = Attendance(
        employee_id=attendance.employee_id,
        attendance_date=attendance.attendance_date,
        check_in=attendance.check_in,
        check_out=attendance.check_out,
        working_hours=attendance.working_hours,
        overtime_hours=attendance.overtime_hours,
        status=attendance.status
    )

    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)

    return db_attendance

def get_attendances(db: Session):
    return db.query(Attendance).all()

def get_attendance(db: Session, attendance_id: int):
    return db.query(Attendance).filter(Attendance.id == attendance_id).first()

def update_attendance(db: Session, attendance_id: int, attendance: AttendanceUpdate):
    db_attendance = get_attendance(db, attendance_id)

    if not db_attendance:
        return None

    update_data = attendance.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_attendance, key, value)

    db.commit()
    db.refresh(db_attendance)

    return db_attendance

def delete_attendance(db: Session, attendance_id: int):
    db_attendance = get_attendance(db, attendance_id)

    if not db_attendance:
        return None

    db.delete(db_attendance)
    db.commit()

    return db_attendance