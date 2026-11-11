import calendar
from datetime import date

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from auth.permissions import has_permission
from models.attendence import Attendance
from models.employee import Employee
from services.attendance import current_datetime


def create_attendance_tools(db: Session, employee_id: int):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise ValueError("Authenticated employee was not found.")

    if not has_permission(db, employee, "attendance:read"):
        return []

    @tool
    def get_my_attendance_history(month: int, year: int) -> dict:
        """Get the authenticated employee's attendance records and summary.

        Args:
            month: Month number from 1 to 12.
            year: Four-digit year from 2000 to 2100.
        """
        if month < 1 or month > 12:
            return {"error": "Month must be between 1 and 12."}
        if year < 2000 or year > 2100:
            return {"error": "Year must be between 2000 and 2100."}

        month_start = date(year, month, 1)
        if month == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month + 1, 1)

        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date >= month_start,
                Attendance.attendance_date < next_month_start,
            )
            .order_by(Attendance.attendance_date)
            .all()
        )
        return {
            "month": calendar.month_name[month],
            "year": year,
            "summary": {
                "recorded_days": len(records),
                "present_days": sum(
                    record.status in {"Present", "Late", "Work From Home"}
                    for record in records
                ),
                "absent_days": sum(
                    record.status == "Absent" for record in records
                ),
                "late_days": sum(
                    record.status == "Late" or record.late_minutes > 0
                    for record in records
                ),
                "work_from_home_days": sum(
                    record.work_mode == "wfh"
                    or record.status == "Work From Home"
                    for record in records
                ),
                "working_hours": round(
                    sum(record.working_hours for record in records),
                    2,
                ),
                "overtime_hours": round(
                    sum(record.overtime_hours for record in records),
                    2,
                ),
            },
            "records": [
                {
                    "date": record.attendance_date.isoformat(),
                    "status": record.status,
                    "work_mode": record.work_mode,
                    "check_in": (
                        record.check_in.isoformat()
                        if record.check_in
                        else None
                    ),
                    "check_out": (
                        record.check_out.isoformat()
                        if record.check_out
                        else None
                    ),
                    "late_minutes": record.late_minutes,
                    "working_hours": record.working_hours,
                    "overtime_hours": record.overtime_hours,
                }
                for record in records
            ],
        }

    @tool
    def get_my_attendance_today() -> dict:
        """Get the authenticated employee's attendance status for today."""
        today = current_datetime().date()
        record = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date == today,
            )
            .first()
        )
        if record is None:
            return {
                "date": today.isoformat(),
                "has_attendance_record": False,
                "message": "No attendance record has been created for today.",
            }

        return {
            "date": today.isoformat(),
            "has_attendance_record": True,
            "status": record.status,
            "work_mode": record.work_mode,
            "check_in": record.check_in.isoformat() if record.check_in else None,
            "check_out": (
                record.check_out.isoformat() if record.check_out else None
            ),
            "working_hours": record.working_hours,
            "overtime_hours": record.overtime_hours,
            "late_minutes": record.late_minutes,
        }

    return [get_my_attendance_history, get_my_attendance_today]
