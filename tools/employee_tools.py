from langchain_core.tools import tool
from sqlalchemy.orm import Session

from models.employee import Employee
from models.attendence import Attendance
from models.leave import Leave
from crud import employee as crud


def create_employee_tools(
    db: Session,
    employee_id: int,
):
    """
    Create tools scoped to the authenticated employee.
    """

    @tool
    def get_my_attendance(month: int, year: int) -> list[dict]:
        """
        Get the authenticated employee's attendance records
        for a specific month and year.

        Args:
            month: Month number from 1 to 12.
            year: Four-digit year.
        """

        if month < 1 or month > 12:
            return [{"error": "Month must be between 1 and 12."}]

        if year < 2000 or year > 2100:
            return [{"error": "Invalid year."}]

        from datetime import date

        start_date = date(year, month, 1)

        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date >= start_date,
                Attendance.attendance_date < end_date,
            )
            .order_by(Attendance.attendance_date)
            .all()
        )

        return [
            {
                "date": str(record.attendance_date),
                "status": record.status,
            }
            for record in records
        ]

    @tool
    def get_my_leave_records() -> list[dict]:
        """
        Get the authenticated employee's leave records.
        """

        records = (
            db.query(Leave)
            .filter(Leave.employee_id == employee_id)
            .order_by(Leave.start_date.desc())
            .all()
        )

        return [
            {
                "status": record.status,
                "start_date": str(record.start_date),
                "end_date": str(record.end_date),
            }
            for record in records
        ]

    @tool
    def get_my_profile() -> dict:
        """
        Get basic profile information for the authenticated employee.
        """

        employee = crud.get_employee(db, employee_id)

        if not employee:
            return {"error": "Employee profile not found."}

        return {
            "employee_id": employee.id,
            "employee_code": employee.employee_code,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "phone": employee.phone,
            "date_of_joining": employee.joining_date,
            "date_of_birth": employee.dob,
            "salary": employee.salary,
            "role": employee.role.name,
            "department": employee.department.name,
            "gender": employee.gender,
            "address": employee.address,
            "status": employee.status
        }

    return [
        get_my_attendance,
        get_my_leave_records,
        get_my_profile,
    ]