from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import employee_scope_query, has_permission
from database import get_db
from models.attendence import Attendance
from models.department import Department
from models.employee import Employee
from models.leave import Leave
from schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
) -> DashboardSummary:
    employee_count = None
    if has_permission(db, current_user, "employee:read"):
        employee_count = (
            employee_scope_query(
                db,
                current_user,
                db.query(Employee),
                Employee.id,
            )
            .filter(Employee.is_active.is_(True))
            .count()
        )

    present_today = None
    if has_permission(db, current_user, "attendance:read"):
        present_today = (
            employee_scope_query(
                db,
                current_user,
                db.query(Attendance),
                Attendance.employee_id,
            )
            .filter(Attendance.attendance_date == date.today())
            .count()
        )

    pending_leaves = None
    if has_permission(db, current_user, "leave:read"):
        pending_leaves = (
            employee_scope_query(
                db,
                current_user,
                db.query(Leave),
                Leave.employee_id,
            )
            .filter(Leave.status == "Pending")
            .count()
        )

    departments = None
    if has_permission(db, current_user, "department:read"):
        departments = (
            db.query(Department)
            .filter(Department.is_active.is_(True))
            .count()
        )

    return DashboardSummary(
        employees=employee_count,
        present_today=present_today,
        pending_leaves=pending_leaves,
        departments=departments,
    )
