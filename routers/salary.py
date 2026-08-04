from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth.permissions import require_permission
from schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
import crud.leave as crud

router = APIRouter()

@router.post(
    "/",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("salary:create"))]
)
def create_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db)
):
    return crud.create_leave(db, leave)

@router.get(
    "/",
    response_model=list[LeaveResponse],
    dependencies=[Depends(require_permission("salary:read"))]
)
def get_leaves(
    db: Session = Depends(get_db)
):
    return crud.get_leaves(db)

@router.get(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("salary:read"))]
)
def get_leave(
    leave_id: int,
    db: Session = Depends(get_db)
):
    leave = crud.get_leave(db, leave_id)

    if not leave:
        raise HTTPException(
            status_code=404,
            detail="Leave not found"
        )

    return leave

@router.patch(
    "/{leave_id}",
    response_model=LeaveResponse,
    dependencies=[Depends(require_permission("salary:update"))]
)
def update_leave(
    leave_id: int,
    leave: LeaveUpdate,
    db: Session = Depends(get_db)
):
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
    dependencies=[Depends(require_permission("salary:delete"))]
)
def delete_leave(
    leave_id: int,
    db: Session = Depends(get_db)
):
    deleted_leave = crud.delete_leave(db, leave_id)

    if not deleted_leave:
        raise HTTPException(
            status_code=404,
            detail="Leave not found"
        )

    return deleted_leave