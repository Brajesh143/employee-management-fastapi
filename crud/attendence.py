from sqlalchemy.orm import Session
from models.attendence import Attendance
from schemas.attendence import AttendanceCreate, AttendanceUpdate
from datetime import datetime, time

def create_attendance(db: Session, attendance: AttendanceCreate):
    db_attendance = Attendance(
        employee_id=attendance.employee_id,
        attendance_date=attendance.attendance_date,
        check_in=attendance.check_in,
        check_out=attendance.check_out,
        working_hours=calculate_working_hours(attendance.check_in, attendance.check_out),
        overtime_hours=attendance.overtime_hours,
        status=calculate_attendance_status(attendance.check_in, attendance.check_out)
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

def get_employee_attendance(db: Session, employee_id: int):
    return db.query(Attendance).filter(Attendance.employee_id == employee_id).all()


def calculate_working_hours(check_in, check_out):

    if not check_in or not check_out:
        return 0

    duration = check_out - check_in

    return round(duration.total_seconds() / 3600, 2)

def calculate_attendance_status(
    check_in: datetime | None,
    check_out: datetime | None,
    is_work_from_home: bool = False,
    is_holiday: bool = False,
    allowed_check_in_time: time = time(9, 30),
):
    # Holiday
    if is_holiday:
        return "Holiday"

    # Work from home
    if is_work_from_home:
        return "Work From Home"

    # No check-in
    if not check_in:
        return "Absent"

    # Employee has checked in but not checked out
    if not check_out:
        return "Late" if check_in.time() > allowed_check_in_time else "Present"

    # Calculate working hours
    working_time = check_out - check_in

    working_hours = working_time.total_seconds() / 3600

    # Less than 4 hours
    if working_hours < 4:
        return "Half Day"

    # Late check-in
    if check_in.time() > allowed_check_in_time:
        return "Late"

    # Normal attendance
    return "Present"