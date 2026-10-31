from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.permissions import require_permission
from crud import designation as crud
from database import get_db
from schemas.designation import (
    DesignationCreate,
    DesignationResponse,
    DesignationUpdate,
)


router = APIRouter()


@router.get(
    "/",
    response_model=list[DesignationResponse],
    dependencies=[Depends(require_permission("employee:read"))],
)
def list_designations(db: Session = Depends(get_db)):
    return crud.get_designations(db)


@router.post(
    "/",
    response_model=DesignationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("employee:create"))],
)
def create_designation(
    designation: DesignationCreate,
    db: Session = Depends(get_db),
):
    return crud.create_designation(db, designation)


@router.patch(
    "/{designation_id}",
    response_model=DesignationResponse,
    dependencies=[Depends(require_permission("employee:update"))],
)
def update_designation(
    designation_id: int,
    designation: DesignationUpdate,
    db: Session = Depends(get_db),
):
    updated = crud.update_designation(db, designation_id, designation)
    if updated is None:
        raise HTTPException(status_code=404, detail="Designation not found")
    return updated
