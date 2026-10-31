from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth.permissions import (
    can_access_employee,
    employee_scope_query,
    has_permission,
    require_permission,
)
from schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
import crud.leave as crud
from models.employee import Employee
from models.leave import Leave

router = APIRouter()

@router.post(
    "/",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:create"))]
)
def create_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:create")),
):
    if not has_permission(db, current_user, "employee:read:all"):
        leave = leave.model_copy(
            update={
                "employee_id": current_user.id,
                "status": "Pending",
                "approved_by": None,
                "approved_at": None,
            }
        )
    return crud.create_leave(db, leave)

@router.get(
    "/",
    response_model=list[LeaveResponse],
    dependencies=[Depends(require_permission("leave:read"))]
)
def get_leaves(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:read")),
):
    return employee_scope_query(
        db,
        current_user,
        db.query(Leave),
        Leave.employee_id,
    ).all()

@router.get(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:read"))]
)
def get_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:read")),
):
    leave = employee_scope_query(
        db,
        current_user,
        db.query(Leave),
        Leave.employee_id,
    ).filter(Leave.id == leave_id).first()

    if not leave:
        raise HTTPException(
            status_code=404,
            detail="Leave not found"
        )

    return leave

@router.patch(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:update"))]
)
def update_leave(
    leave_id: int,
    leave: LeaveUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:update")),
):
    accessible_leave = employee_scope_query(
        db,
        current_user,
        db.query(Leave),
        Leave.employee_id,
    ).filter(Leave.id == leave_id).first()
    if accessible_leave is None:
        raise HTTPException(status_code=404, detail="Leave not found")

    updated_leave = crud.update_leave(db, leave_id, leave)

    if not updated_leave:
        raise HTTPException(
            status_code=404,
            detail="Leave not found"
        )

    return updated_leave

@router.delete(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:delete"))]
)
def delete_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:delete")),
):
    accessible_leave = employee_scope_query(
        db,
        current_user,
        db.query(Leave),
        Leave.employee_id,
    ).filter(Leave.id == leave_id).first()
    if accessible_leave is None:
        raise HTTPException(status_code=404, detail="Leave not found")

    deleted_leave = crud.delete_leave(db, leave_id)

    if not deleted_leave:
        raise HTTPException(
            status_code=404,
            detail="Leave not found"
        )

    return deleted_leave

@router.get(
    "/employee/{employee_id}",
    response_model=list[LeaveResponse],
    dependencies=[Depends(require_permission("leave:read"))]
)
def get_employee_leave(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:read")),
):
    if not can_access_employee(db, current_user, employee_id):
        raise HTTPException(status_code=404, detail="Leave record not found")

    leaves = crud.get_my_leaves(db, employee_id)
    
    if not leaves:
        raise HTTPException(
            status_code=404,
            detail="Leave record not found"
        )

    return leaves

@router.put("/{leave_id}/{status}")
def approve_leave_request(
    leave_id: int,
    status: str,
    current_user: Employee = Depends(
        require_permission("leave:approve")
    ),
    db: Session = Depends(get_db)
):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if leave is None or not can_access_employee(
        db,
        current_user,
        leave.employee_id,
        include_self=False,
    ):
        raise HTTPException(status_code=404, detail="Leave not found")

    return crud.approve_leave(
        db=db,
        leave_id=leave_id,
        status=status,
        approved_by=current_user.id
    )
