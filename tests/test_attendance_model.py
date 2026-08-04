from datetime import date, datetime

from models.attendence import Attendance


def test_attendance_model_can_be_instantiated():
    attendance = Attendance(
        employee_id=1,
        attendance_date=date(2024, 1, 15),
        check_in=datetime(2024, 1, 15, 9, 0),
        check_out=datetime(2024, 1, 15, 17, 0),
        working_hours=8.0,
        overtime_hours=0.0,
        status="Present",
    )

    assert attendance.status == "Present"
