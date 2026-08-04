from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from auth.permissions import require_permission
from models.employee import Employee
from schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from database import get_db
from crud import employee as crud
from auth.dependencies import get_current_user

router = APIRouter()

# @router.post(
#     "/",
#     dependencies=[
#         Depends(
#             require_permission("employee:create")
#         )
#     ],
#     response_model=EmployeeResponse
# )
# def create_employee(
#     employee: EmployeeCreate,
#     db: Session = Depends(get_db)
# ):
#     return crud.create_employee(
#         db,
#         employee
#     )

@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("employee:create"))
    ]
)
def create_employee_api(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):

    return crud.create_employee(db, employee)

@router.get(
    "/",
    response_model=list[EmployeeResponse],
    dependencies=[Depends(require_permission("employee:read"))]
)
def get_employees(
    db: Session = Depends(get_db)
):
    return crud.get_employees(db)

@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:read"))]
)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = crud.get_employee(
        db,
        employee_id
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    return employee

@router.patch(
    "/{employee_id}",
    response_model=EmployeeUpdate,
    dependencies=[Depends(require_permission("employee:update"))]
)
def update_employee(
    employee_id: int,
    employee: EmployeeUpdate,
    db: Session = Depends(get_db)
):
    updated_employee = crud.update_employee(
        employee_id,
        employee,
        db
    )

    if not updated_employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    return updated_employee

@router.delete(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:delete"))]
)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    deleted_employee = crud.delete_employee(
        db,
        employee_id
    )

    if not deleted_employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    return deleted_employee
