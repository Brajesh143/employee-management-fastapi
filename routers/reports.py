from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import require_permission
from database import get_db
from models.employee import Employee
from services import attendance as attendance_service

router = APIRouter()


@router.get(
    "/attendance",
    dependencies=[Depends(require_permission("report:read"))],
)
def attendance_report(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.build_attendance_report(
        db,
        current_user,
        start=from_,
        end=to,
        department_id=department_id,
    )
