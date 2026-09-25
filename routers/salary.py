from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth.permissions import require_permission
from schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
from schemas.salary import SalaryCreate, SalaryResponse, SalaryUpdate
import crud.salary as crud

router = APIRouter()

@router.post(
    "/",
    response_model=SalaryResponse,
    dependencies=[Depends(require_permission("salary:create"))]
)
def create_salary(
    leave: SalaryCreate,
    db: Session = Depends(get_db)
):
    return crud.create_salary(db, leave)

@router.get(
    "/",
    response_model=list[SalaryResponse],
    dependencies=[Depends(require_permission("salary:read"))]
)
def get_salary(
    db: Session = Depends(get_db)
):
    return crud.get_salaries(db)

@router.get(
    "/{salary_id}",
    response_model=SalaryResponse,
    dependencies=[Depends(require_permission("salary:read"))]
)
def get_salary(
    salary_id: int,
    db: Session = Depends(get_db)
):
    salary = crud.get_salary(db, salary_id)

    if not salary:
        raise HTTPException(
            status_code=404,
            detail="Salary not found"
        )

    return salary

@router.patch(
    "/{salary_id}",
    response_model=SalaryResponse,
    dependencies=[Depends(require_permission("salary:update"))]
)
def update_salary(
    salary_id: int,
    salary: SalaryUpdate,
    db: Session = Depends(get_db)
):
    updated_salary = crud.update_salary(db, salary_id, salary)

    if not updated_salary:
        raise HTTPException(
            status_code=404,
            detail="Salary not found"
        )

    return updated_salary

@router.delete(
    "/{salary_id}",
    response_model=SalaryResponse,
    dependencies=[Depends(require_permission("salary:delete"))]
)
def delete_salary(
    salary_id: int,
    db: Session = Depends(get_db)
):
    deleted_salary = crud.delete_salary(db, salary_id)

    if not deleted_salary:
        raise HTTPException(
            status_code=404,
            detail="Salary not found"
        )

    return deleted_salary