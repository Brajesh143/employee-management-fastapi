from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth.permissions import (
    can_access_employee,
    employee_scope_query,
    has_permission,
    require_any_permission,
    require_permission,
)
from database import get_db
from models.employee import Employee
from models.leave import Leave
from schemas.leave import (
    LeaveBalanceResponse,
    LeaveBalanceUpdate,
    LeaveCancellation,
    LeaveCreate,
    LeaveResponse,
    LeaveReviewResponse,
    LeaveUpdate,
)
import crud.leave as crud

router = APIRouter()


@router.post(
    "/",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:create")),
):
    return crud.create_leave(
        db,
        leave,
        employee=current_user,
        actor_id=current_user.id,
    )


@router.get(
    "/",
    response_model=list[LeaveResponse],
    dependencies=[Depends(require_permission("leave:read"))],
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
    ).order_by(Leave.created_at.desc(), Leave.id.desc()).all()


@router.get(
    "/balance/me",
    response_model=LeaveBalanceResponse,
    dependencies=[Depends(require_permission("leave:read"))],
)
def get_my_leave_balance(
    current_user: Employee = Depends(require_permission("leave:read")),
):
    return {
        "employee_id": current_user.id,
        "leave_balance": current_user.leave_balance,
    }


@router.get(
    "/balance/{employee_id}",
    response_model=LeaveBalanceResponse,
    dependencies=[Depends(require_permission("leave:read"))],
)
def get_employee_leave_balance(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:read")),
):
    if not can_access_employee(db, current_user, employee_id):
        raise HTTPException(status_code=404, detail="Leave balance not found.")
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Leave balance not found.")
    return {
        "employee_id": employee.id,
        "leave_balance": employee.leave_balance,
    }


@router.patch(
    "/balance/{employee_id}",
    response_model=LeaveBalanceResponse,
    dependencies=[Depends(require_permission("leave:balance:manage"))],
)
def set_employee_leave_balance(
    employee_id: int,
    payload: LeaveBalanceUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_permission("leave:balance:manage")
    ),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    updated_employee = crud.update_leave_balance(
        db,
        employee,
        payload.leave_balance,
        actor_id=current_user.id,
    )
    return {
        "employee_id": updated_employee.id,
        "leave_balance": updated_employee.leave_balance,
    }


@router.get(
    "/reports",
    dependencies=[
        Depends(require_any_permission("report:read", "report:team:read"))
    ],
)
def leave_report(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    leave_status: Literal["Pending", "Approved", "Rejected", "Cancelled"] | None = None,
    leave_type: Literal["Sick", "Casual", "Earned", "Maternity", "Paternity"] | None = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_any_permission("report:read", "report:team:read")),
):
    if not has_permission(db, current_user, "leave:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view leave reports.",
        )
    if to_date < from_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'to' date cannot be before 'from' date.",
        )
    query = employee_scope_query(
        db,
        current_user,
        db.query(Leave),
        Leave.employee_id,
    )
    return crud.build_leave_report(
        db,
        query,
        start_date=from_date,
        end_date=to_date,
        leave_status=leave_status,
        leave_type=leave_type,
    )


@router.get(
    "/employee/{employee_id}",
    response_model=list[LeaveResponse],
    dependencies=[Depends(require_permission("leave:read"))],
)
def get_employee_leave(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:read")),
):
    if not can_access_employee(db, current_user, employee_id):
        raise HTTPException(status_code=404, detail="Leave record not found.")
    return crud.get_my_leaves(db, employee_id)


@router.get(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:read"))],
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
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave not found.")
    return leave


@router.patch(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:update"))],
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
        raise HTTPException(status_code=404, detail="Leave not found.")
    updated_leave = crud.update_leave(
        db,
        leave_id,
        leave,
        actor_id=current_user.id,
    )
    if updated_leave is None:
        raise HTTPException(status_code=404, detail="Leave not found.")
    return updated_leave


@router.delete(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:delete"))],
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
        raise HTTPException(status_code=404, detail="Leave not found.")
    deleted_leave = crud.delete_leave(
        db,
        leave_id,
        actor_id=current_user.id,
    )
    if deleted_leave is None:
        raise HTTPException(status_code=404, detail="Leave not found.")
    return deleted_leave


@router.post(
    "/{leave_id}/cancel",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("leave:cancel"))],
)
def cancel_leave(
    leave_id: int,
    payload: LeaveCancellation = LeaveCancellation(),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:cancel")),
):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if leave is None or not can_access_employee(
        db,
        current_user,
        leave.employee_id,
    ):
        raise HTTPException(status_code=404, detail="Leave not found.")
    if (
        leave.employee_id != current_user.id
        and not has_permission(db, current_user, "leave:balance:manage")
    ):
        raise HTTPException(status_code=404, detail="Leave not found.")
    return crud.cancel_leave(
        db,
        leave,
        actor_id=current_user.id,
        reason=payload.reason,
    )


@router.put(
    "/{leave_id}/{decision}",
    response_model=LeaveReviewResponse,
    dependencies=[Depends(require_permission("leave:approve"))],
)
def review_leave_request(
    leave_id: int,
    decision: Literal["approved", "rejected"],
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("leave:approve")),
):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if (
        leave is None
        or leave.employee_id == current_user.id
        or not can_access_employee(
            db,
            current_user,
            leave.employee_id,
            include_self=False,
        )
    ):
        raise HTTPException(status_code=404, detail="Leave not found.")
    return crud.approve_leave(
        db=db,
        leave_id=leave_id,
        decision=decision,
        reviewer=current_user,
    )
