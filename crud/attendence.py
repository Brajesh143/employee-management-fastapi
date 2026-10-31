from datetime import datetime, time

from sqlalchemy.orm import Session

from models.attendence import Attendance
from schemas.attendence import AttendanceCreate, AttendanceUpdate
from services.attendance import apply_metrics, get_or_create_default_shift


def create_attendance(db: Session, attendance: AttendanceCreate):
    shift = get_or_create_default_shift(db)
    db_attendance = Attendance(
        employee_id=attendance.employee_id,
        attendance_date=attendance.attendance_date,
        check_in=attendance.check_in,
        check_out=attendance.check_out,
        overtime_hours=attendance.overtime_hours or 0,
        work_mode="office",
        source="web",
        shift_id=shift.id,
    )
    apply_metrics(db_attendance, shift)
    if attendance.status:
        db_attendance.status = attendance.status

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
    if is_holiday:
        return "Holiday"
    if is_work_from_home:
        return "Work From Home"
    if not check_in:
        return "Absent"
    if not check_out:
        return "Late" if check_in.time() > allowed_check_in_time else "Present"

    working_hours = (check_out - check_in).total_seconds() / 3600
    if working_hours < 4:
        return "Half Day"
    if check_in.time() > allowed_check_in_time:
        return "Late"
    return "Present"
