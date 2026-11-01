from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import employee_scope_query, has_permission, require_permission
from database import get_db
from models.attendence import Attendance
from models.employee import Employee
import crud.attendence as crud
from schemas.attendence import (
    AttendanceCreate,
    AttendancePolicyResponse,
    AttendancePolicyUpdate,
    AttendanceResponse,
    AttendanceUpdate,
    CheckInRequest,
    CheckOutRequest,
    CorrectionCreate,
    CorrectionResponse,
    NotificationResponse,
    ReviewRequest,
    WfhRequestCreate,
    WfhRequestResponse,
)
from services import attendance as attendance_service

router = APIRouter()


@router.post(
    "/check-in",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_permission("attendance:create"))],
)
def check_in(
    payload: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.check_in(
        db,
        current_user,
        work_mode=payload.work_mode,
        source=payload.source,
        notes=payload.notes,
    )


@router.post(
    "/check-out",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_permission("attendance:create"))],
)
def check_out(
    payload: CheckOutRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    notes = payload.notes if payload else None
    return attendance_service.check_out(db, current_user, notes=notes)


@router.get(
    "/today",
    response_model=AttendanceResponse | None,
    dependencies=[Depends(require_permission("attendance:read"))],
)
def get_today_attendance(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    today = attendance_service.current_datetime().date()
    return (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == current_user.id,
            Attendance.attendance_date == today,
        )
        .first()
    )


@router.get(
    "/policy",
    response_model=AttendancePolicyResponse,
    dependencies=[Depends(require_permission("attendance:read"))],
)
def get_policy(db: Session = Depends(get_db)):
    return attendance_service.get_or_create_policy(db)


@router.patch(
    "/policy",
    response_model=AttendancePolicyResponse,
    dependencies=[Depends(require_permission("attendance:update"))],
)
def patch_policy(
    payload: AttendancePolicyUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.update_policy(
        db, current_user, allow_direct_wfh=payload.allow_direct_wfh
    )


@router.post(
    "/wfh-requests",
    response_model=WfhRequestResponse,
    dependencies=[Depends(require_permission("attendance:create"))],
)
def create_wfh_request(
    payload: WfhRequestCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.create_wfh_request(
        db,
        current_user,
        request_date=payload.request_date,
        reason=payload.reason,
    )


@router.get(
    "/wfh-requests",
    response_model=list[WfhRequestResponse],
    dependencies=[Depends(require_permission("attendance:read"))],
)
def list_wfh_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.list_wfh_requests(
        db, current_user, status_filter=status_filter
    )


@router.post(
    "/wfh-requests/{request_id}/approve",
    response_model=WfhRequestResponse,
    dependencies=[Depends(require_permission("attendance:wfh"))],
)
def approve_wfh_request(
    request_id: int,
    payload: ReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.review_wfh_request(
        db,
        current_user,
        request_id,
        approved=True,
        comment=payload.comment if payload else None,
    )


@router.post(
    "/wfh-requests/{request_id}/reject",
    response_model=WfhRequestResponse,
    dependencies=[Depends(require_permission("attendance:wfh"))],
)
def reject_wfh_request(
    request_id: int,
    payload: ReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.review_wfh_request(
        db,
        current_user,
        request_id,
        approved=False,
        comment=payload.comment if payload else None,
    )


@router.post(
    "/corrections",
    response_model=CorrectionResponse,
    dependencies=[Depends(require_permission("attendance:create"))],
)
def create_correction(
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.create_correction(
        db,
        current_user,
        original_attendance_id=payload.original_attendance_id,
        requested_check_in=payload.requested_check_in,
        requested_check_out=payload.requested_check_out,
        requested_work_mode=payload.requested_work_mode,
        reason=payload.reason,
    )


@router.get(
    "/corrections",
    response_model=list[CorrectionResponse],
    dependencies=[Depends(require_permission("attendance:read"))],
)
def list_corrections(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.list_corrections(
        db, current_user, status_filter=status_filter
    )


@router.post(
    "/corrections/{correction_id}/approve",
    response_model=CorrectionResponse,
    dependencies=[Depends(require_permission("attendance:correct"))],
)
def approve_correction(
    correction_id: int,
    payload: ReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.review_correction(
        db,
        current_user,
        correction_id,
        approved=True,
        comment=payload.comment if payload else None,
    )


@router.post(
    "/corrections/{correction_id}/reject",
    response_model=CorrectionResponse,
    dependencies=[Depends(require_permission("attendance:correct"))],
)
def reject_correction(
    correction_id: int,
    payload: ReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.review_correction(
        db,
        current_user,
        correction_id,
        approved=False,
        comment=payload.comment if payload else None,
    )


@router.get(
    "/employee/{employee_id}",
    response_model=list[AttendanceResponse],
    dependencies=[Depends(require_permission("attendance:read"))],
)
def get_employee_attendence(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return employee_scope_query(
        db,
        current_user,
        db.query(Attendance),
        Attendance.employee_id,
    ).filter(Attendance.employee_id == employee_id).all()


@router.post(
    "/",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_permission("attendance:manage"))],
)
def create_attendance(
    attendance: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    if not has_permission(db, current_user, "employee:read:all"):
        attendance = attendance.model_copy(update={"employee_id": current_user.id})
    return crud.create_attendance(
        db,
        attendance,
        actor_id=current_user.id,
    )


@router.get(
    "/",
    response_model=list[AttendanceResponse],
    dependencies=[Depends(require_permission("attendance:read"))],
)
def get_attendances(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return employee_scope_query(
        db,
        current_user,
        db.query(Attendance),
        Attendance.employee_id,
    ).all()


@router.get(
    "/{attendance_id}",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_permission("attendance:read"))],
)
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    attendance = employee_scope_query(
        db,
        current_user,
        db.query(Attendance),
        Attendance.employee_id,
    ).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return attendance


@router.patch(
    "/{attendance_id}",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_permission("attendance:update"))],
)
def update_attendance(
    attendance_id: int,
    attendance: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    existing = employee_scope_query(
        db,
        current_user,
        db.query(Attendance),
        Attendance.employee_id,
    ).filter(Attendance.id == attendance_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    updated_attendance = crud.update_attendance(
        db,
        attendance_id,
        attendance,
        actor_id=current_user.id,
    )
    if not updated_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return updated_attendance


@router.delete(
    "/{attendance_id}",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_permission("attendance:delete"))],
)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    existing = employee_scope_query(
        db,
        current_user,
        db.query(Attendance),
        Attendance.employee_id,
    ).filter(Attendance.id == attendance_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    deleted_attendance = crud.delete_attendance(
        db,
        attendance_id,
        actor_id=current_user.id,
    )
    if not deleted_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return deleted_attendance
