from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth.permissions import require_permission
from schemas.attendence import AttendanceCreate, AttendanceUpdate, AttendenceByEmployee, AttendanceResponse
import crud.attendence as crud

router = APIRouter()

@router.post(
    "/",
    response_model=AttendanceCreate,
    dependencies=[Depends(require_permission("attendance:create"))]
)
def create_attendance(
    attendance: AttendanceCreate,
    db: Session = Depends(get_db)
):
    return crud.create_attendance(db, attendance)

@router.get(
    "/",
    response_model=list[AttendanceCreate],
    dependencies=[Depends(require_permission("attendance:read"))]
)
def get_attendances(
    db: Session = Depends(get_db)
):
    return crud.get_attendances(db)

@router.get(
    "/{attendance_id}",
    response_model=AttendanceCreate,
    dependencies=[Depends(require_permission("attendance:read"))]
)
def get_attendance(attendance_id: int, db: Session = Depends(get_db)):
    attendance = crud.get_attendance(db, attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found"
        )

    return attendance

@router.patch(
    "/{attendance_id}",
    response_model=AttendanceUpdate,
    dependencies=[Depends(require_permission("attendance:update"))]
)
def update_attendance(
    attendance_id: int,
    attendance: AttendanceUpdate,
    db: Session = Depends(get_db)
):
    updated_attendance = crud.update_attendance(db, attendance_id, attendance)

    if not updated_attendance:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found"
        )

    return updated_attendance

@router.delete(
    "/{attendance_id}",
    response_model=AttendanceCreate,
    dependencies=[Depends(require_permission("attendance:delete"))]
)
def delete_attendance(attendance_id: int, db: Session = Depends(get_db)):
    deleted_attendance = crud.delete_attendance(db, attendance_id)

    if not deleted_attendance:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found"
        )

    return deleted_attendance

@router.get(
    "/employee/{employee_id}",
    response_model=list[AttendanceResponse],
    dependencies=[Depends(require_permission("attendance:read"))]
)
def get_employee_attendence(employee_id: int, db: Session = Depends(get_db)):
    print("employeeid====", employee_id)
    attendance = crud.get_employee_attendance(db, employee_id)
    
    if not attendance:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found"
        )

    return attendance