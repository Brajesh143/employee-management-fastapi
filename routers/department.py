from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth.permissions import require_permission
from schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate
)

import crud.department as crud
from fastapi import HTTPException

router = APIRouter()

@router.post(
    "/",
    response_model=DepartmentResponse,
    dependencies=[Depends(require_permission("department:create"))]
)
def create_department(
    department: DepartmentCreate,
    db: Session = Depends(get_db)
):

    return crud.create_department(
        db,
        department
    )

@router.get(
    "/",
    response_model=list[DepartmentResponse],
    dependencies=[Depends(require_permission("department:read"))]
)
def get_departments(
    db: Session = Depends(get_db)
):

    return crud.get_departments(db)

@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    dependencies=[Depends(require_permission("department:read"))]
)
def get_department(department_id: int, db: Session = Depends(get_db)):
    department = crud.get_department(
        db,
        department_id
    )

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Department not found"
        )

    return department

@router.patch(
    "/{department_id}",
    response_model=DepartmentUpdate,
    dependencies=[Depends(require_permission("department:update"))]
)
def update_department(
    department_id: int,
    department: DepartmentUpdate,
    db: Session = Depends(get_db)
):

    update_department = crud.update_department(
        department_id,
        department,
        db
    )

    if not update_department:
        raise HTTPException(
                status_code=404,
                detail="Department not found"
            )

    return update_department

@router.delete(
    "/{department_id}",
    response_model=DepartmentResponse,
    dependencies=[Depends(require_permission("department:delete"))]
)
def delete_department(department_id: int, db: Session = Depends(get_db)):
    deleted_department = crud.delete_department(
        db,
        department_id
    )

    if not deleted_department:
        raise HTTPException(
            status_code=404,
            detail="Department not found"
        )

    return deleted_department