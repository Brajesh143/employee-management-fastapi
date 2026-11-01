from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from auth.permissions import has_permission
from models.employee import Employee
from models.leave import Leave
from schemas.leave import LeaveCreate, LeaveUpdate
from services.audit import write_audit_log


ACTIVE_LEAVE_STATUSES = ("Pending", "Approved")


def leave_snapshot(leave: Leave) -> dict[str, object]:
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "leave_type": leave.leave_type,
        "start_date": leave.start_date,
        "end_date": leave.end_date,
        "total_days": leave.total_days,
        "reason": leave.reason,
        "status": leave.status,
        "approval_stage": leave.approval_stage,
        "manager_approved_by": leave.manager_approved_by,
        "manager_approved_at": leave.manager_approved_at,
        "hr_approved_by": leave.hr_approved_by,
        "hr_approved_at": leave.hr_approved_at,
        "approved_by": leave.approved_by,
        "approved_at": leave.approved_at,
        "rejected_by": leave.rejected_by,
        "rejected_at": leave.rejected_at,
        "cancelled_by": leave.cancelled_by,
        "cancelled_at": leave.cancelled_at,
        "cancellation_reason": leave.cancellation_reason,
    }


def create_leave(
    db: Session,
    leave: LeaveCreate,
    *,
    employee: Employee,
    actor_id: int,
) -> Leave:
    _ensure_no_overlap(
        db,
        employee_id=employee.id,
        start_date=leave.start_date,
        end_date=leave.end_date,
    )
    db_leave = Leave(
        employee_id=employee.id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        total_days=calculate_total_days(leave.start_date, leave.end_date),
        reason=leave.reason.strip(),
        status="Pending",
        approval_stage=(
            "manager" if employee.reporting_manager_id is not None else "hr"
        ),
    )
    db.add(db_leave)
    db.flush()
    write_audit_log(
        db,
        actor_id=actor_id,
        action="leave.create",
        resource_type="leave",
        resource_id=db_leave.id,
        after=leave_snapshot(db_leave),
    )
    db.commit()
    db.refresh(db_leave)
    return db_leave


def get_leaves(db: Session):
    return db.query(Leave).order_by(Leave.created_at.desc(), Leave.id.desc()).all()


def get_leave(db: Session, leave_id: int) -> Leave | None:
    return db.query(Leave).filter(Leave.id == leave_id).first()


def update_leave(
    db: Session,
    leave_id: int,
    leave: LeaveUpdate,
    *,
    actor_id: int,
) -> Leave | None:
    db_leave = get_leave(db, leave_id)
    if db_leave is None:
        return None
    if db_leave.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be edited.",
        )

    update_data = leave.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one leave field to update.",
        )
    new_start = update_data.get("start_date", db_leave.start_date)
    new_end = update_data.get("end_date", db_leave.end_date)
    if new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End date cannot be before start date.",
        )
    _ensure_no_overlap(
        db,
        employee_id=db_leave.employee_id,
        start_date=new_start,
        end_date=new_end,
        exclude_leave_id=db_leave.id,
    )

    before = leave_snapshot(db_leave)
    for key, value in update_data.items():
        setattr(db_leave, key, value.strip() if key == "reason" else value)
    db_leave.total_days = calculate_total_days(new_start, new_end)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="leave.update",
        resource_type="leave",
        resource_id=db_leave.id,
        before=before,
        after=leave_snapshot(db_leave),
    )
    db.commit()
    db.refresh(db_leave)
    return db_leave


def delete_leave(
    db: Session,
    leave_id: int,
    *,
    actor_id: int,
) -> Leave | None:
    db_leave = get_leave(db, leave_id)
    if db_leave is None:
        return None
    if db_leave.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be deleted.",
        )
    before = leave_snapshot(db_leave)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="leave.delete",
        resource_type="leave",
        resource_id=db_leave.id,
        before=before,
    )
    db.delete(db_leave)
    db.commit()
    return db_leave


def get_my_leaves(db: Session, employee_id: int) -> list[Leave]:
    return (
        db.query(Leave)
        .filter(Leave.employee_id == employee_id)
        .order_by(Leave.start_date.desc(), Leave.id.desc())
        .all()
    )


def calculate_total_days(start_date: date, end_date: date) -> int:
    return (end_date - start_date).days + 1


def approve_leave(
    db: Session,
    leave_id: int,
    decision: str,
    reviewer: Employee,
) -> dict[str, object]:
    leave = get_leave(db, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if leave.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Leave is already {leave.status.lower()}.",
        )
    if decision not in {"approved", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Decision must be 'approved' or 'rejected'.",
        )
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    before = leave_snapshot(leave)
    is_hr_reviewer = has_permission(db, reviewer, "leave:balance:manage")
    if leave.approval_stage == "manager":
        if employee.reporting_manager_id != reviewer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the employee's assigned manager can review this stage.",
            )
        if decision == "approved":
            leave.manager_approved_by = reviewer.id
            leave.manager_approved_at = datetime.utcnow()
            leave.approval_stage = "hr"
            action = "leave.manager_approve"
        else:
            leave.status = "Rejected"
            leave.approval_stage = "rejected"
            leave.rejected_by = reviewer.id
            leave.rejected_at = datetime.utcnow()
            action = "leave.manager_reject"
    elif leave.approval_stage == "hr":
        if not is_hr_reviewer:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR leave approval is required for this stage.",
            )
        if leave.manager_approved_by == reviewer.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A different reviewer must complete the HR approval stage.",
            )
        if decision == "approved":
            if employee.leave_balance < leave.total_days:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Insufficient leave balance. Available: "
                        f"{employee.leave_balance}, requested: {leave.total_days}."
                    ),
                )
            employee.leave_balance -= leave.total_days
            leave.hr_approved_by = reviewer.id
            leave.hr_approved_at = datetime.utcnow()
            leave.approved_by = reviewer.id
            leave.approved_at = leave.hr_approved_at
            leave.status = "Approved"
            leave.approval_stage = "completed"
            action = "leave.hr_approve"
        else:
            leave.status = "Rejected"
            leave.approval_stage = "rejected"
            leave.rejected_by = reviewer.id
            leave.rejected_at = datetime.utcnow()
            action = "leave.hr_reject"
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This leave request is not awaiting approval.",
        )

    write_audit_log(
        db,
        actor_id=reviewer.id,
        action=action,
        resource_type="leave",
        resource_id=leave.id,
        before=before,
        after=leave_snapshot(leave),
    )
    db.commit()
    db.refresh(leave)
    db.refresh(employee)
    return {
        "message": f"Leave {leave.status.lower() if leave.status != 'Pending' else 'moved to HR review'} successfully.",
        "leave": leave,
        "remaining_leave_balance": employee.leave_balance,
    }


def cancel_leave(
    db: Session,
    leave: Leave,
    *,
    actor_id: int,
    reason: str | None,
) -> Leave:
    if leave.status not in {"Pending", "Approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {leave.status.lower()} leave request cannot be cancelled.",
        )
    if leave.status == "Approved" and leave.start_date <= date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approved leave can only be cancelled before it starts.",
        )

    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    before = leave_snapshot(leave)
    if leave.status == "Approved":
        employee.leave_balance += leave.total_days
    leave.status = "Cancelled"
    leave.approval_stage = "cancelled"
    leave.cancelled_by = actor_id
    leave.cancelled_at = datetime.utcnow()
    leave.cancellation_reason = reason.strip() if reason else None
    write_audit_log(
        db,
        actor_id=actor_id,
        action="leave.cancel",
        resource_type="leave",
        resource_id=leave.id,
        before=before,
        after=leave_snapshot(leave),
    )
    db.commit()
    db.refresh(leave)
    return leave


def update_leave_balance(
    db: Session,
    employee: Employee,
    new_balance: float,
    *,
    actor_id: int,
) -> Employee:
    before = {
        "employee_id": employee.id,
        "leave_balance": employee.leave_balance,
    }
    employee.leave_balance = new_balance
    write_audit_log(
        db,
        actor_id=actor_id,
        action="leave.balance.update",
        resource_type="employee",
        resource_id=employee.id,
        before=before,
        after={
            "employee_id": employee.id,
            "leave_balance": employee.leave_balance,
        },
    )
    db.commit()
    db.refresh(employee)
    return employee


def build_leave_report(
    db: Session,
    query,
    *,
    start_date: date,
    end_date: date,
    leave_status: str | None = None,
    leave_type: str | None = None,
) -> dict[str, object]:
    filtered = query.filter(
        Leave.start_date <= end_date,
        Leave.end_date >= start_date,
    )
    if leave_status:
        filtered = filtered.filter(Leave.status == leave_status)
    if leave_type:
        filtered = filtered.filter(Leave.leave_type == leave_type)
    leaves = filtered.order_by(Leave.start_date, Leave.id).all()

    totals: dict[str, int | float] = {
        "requests": len(leaves),
        "requested_days": sum(
            (min(leave.end_date, end_date) - max(leave.start_date, start_date)).days
            + 1
            for leave in leaves
        ),
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "cancelled": 0,
    }
    for leave in leaves:
        totals[leave.status.lower()] += 1
    return {
        "from_date": start_date,
        "to_date": end_date,
        "totals": totals,
        "leaves": leaves,
    }


def _ensure_no_overlap(
    db: Session,
    *,
    employee_id: int,
    start_date: date,
    end_date: date,
    exclude_leave_id: int | None = None,
) -> None:
    query = db.query(Leave).filter(
        Leave.employee_id == employee_id,
        Leave.status.in_(ACTIVE_LEAVE_STATUSES),
        Leave.start_date <= end_date,
        Leave.end_date >= start_date,
    )
    if exclude_leave_id is not None:
        query = query.filter(Leave.id != exclude_leave_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This leave overlaps an existing pending or approved request.",
        )
