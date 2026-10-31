from datetime import date

from pydantic import BaseModel


class AttendanceReportEmployee(BaseModel):
    employee_id: int
    employee_code: str
    name: str
    department_id: int | None
    present_days: int
    absent_days: int
    late_days: int
    wfh_days: int
    office_days: int
    overtime_hours: float
    unpaid_days: int


class AttendanceReportTotals(BaseModel):
    present_days: int
    absent_days: int
    late_days: int
    wfh_days: int
    office_days: int
    overtime_hours: float
    unpaid_days: int
    working_days: int


class AttendanceReportResponse(BaseModel):
    from_: date
    to: date
    department_id: int | None
    working_days: int
    totals: AttendanceReportTotals
    employees: list[AttendanceReportEmployee]

    model_config = {"populate_by_name": True}
