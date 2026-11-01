from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import (
    has_permission,
    require_any_permission,
    require_permission,
)
from database import get_db
from models.employee import Employee
from models.salary import Salary
from schemas.salary import (
    PayslipResponse,
    PayrollRunResponse,
    SalaryCreate,
    SalaryResponse,
    SalaryStructureCreate,
    SalaryStructureResponse,
    SalaryUpdate,
)
from crud import salary as crud

router = APIRouter()


@router.post(
    "/structures",
    response_model=SalaryStructureResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("salary:create"))],
)
def create_salary_structure(
    payload: SalaryStructureCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return crud.create_salary_structure(
        db,
        payload,
        actor_id=current_user.id,
    )


@router.get(
    "/structures",
    response_model=list[SalaryStructureResponse],
    dependencies=[Depends(require_permission("salary:read"))],
)
def list_salary_structures(
    employee_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    if employee_id is not None and not has_permission(
        db,
        current_user,
        "salary:read",
    ):
        if employee_id != current_user.id:
            raise HTTPException(status_code=404, detail="Salary structure not found.")
    if not has_permission(db, current_user, "salary:read"):
        employee_id = current_user.id
    return crud.get_salary_structures(db, employee_id=employee_id)


@router.post(
    "/",
    response_model=SalaryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("salary:create"))],
)
def create_salary(
    payload: SalaryCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return crud.create_salary(db, payload, actor_id=current_user.id)


@router.get(
    "/",
    response_model=list[SalaryResponse],
    dependencies=[Depends(require_any_permission("salary:read", "payslip:read"))],
)
def list_salaries(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2200),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("salary:read", "payslip:read")
    ),
):
    if has_permission(db, current_user, "salary:read"):
        return crud.get_salaries(db, month=month, year=year)
    return crud.get_salary_by_employee(
        db,
        current_user.id,
        month=month,
        year=year,
    )


@router.get(
    "/employee/{employee_id}",
    response_model=list[SalaryResponse],
    dependencies=[Depends(require_any_permission("salary:read", "payslip:read"))],
)
def get_employee_salary(
    employee_id: int,
    year: int | None = Query(default=None, ge=2000, le=2200),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("salary:read", "payslip:read")
    ),
):
    if not has_permission(db, current_user, "salary:read"):
        if employee_id != current_user.id:
            raise HTTPException(status_code=404, detail="Salary record not found.")
    return crud.get_salary_by_employee(
        db,
        employee_id,
        year=year,
        month=month,
    )


@router.get(
    "/{salary_id}/payslip",
    response_model=PayslipResponse,
    dependencies=[Depends(require_any_permission("salary:read", "payslip:read"))],
)
def get_payslip(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("salary:read", "payslip:read")
    ),
):
    salary = crud.get_salary(db, salary_id)
    if salary is None:
        raise HTTPException(status_code=404, detail="Payslip not found.")
    if not has_permission(db, current_user, "salary:read"):
        if salary.employee_id != current_user.id:
            raise HTTPException(status_code=404, detail="Payslip not found.")
    employee = db.query(Employee).filter(Employee.id == salary.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Payslip not found.")
    return {
        "id": salary.id,
        "employee_id": salary.employee_id,
        "month": salary.month,
        "year": salary.year,
        "basic_salary": salary.basic_salary,
        "hra": salary.hra,
        "allowance": salary.allowance,
        "bonus": salary.bonus,
        "deduction": salary.deduction,
        "tax": salary.tax,
        "net_salary": salary.net_salary,
        "payment_status": salary.payment_status,
        "payment_date": salary.payment_date,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "employee_code": employee.employee_code,
        "email": employee.email,
    }


@router.get(
    "/{salary_id}/payslip/download",
    dependencies=[Depends(require_any_permission("salary:read", "payslip:read"))],
)
def download_payslip(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("salary:read", "payslip:read")
    ),
):
    salary = crud.get_salary(db, salary_id)
    if salary is None:
        raise HTTPException(status_code=404, detail="Payslip not found.")
    if (
        not has_permission(db, current_user, "salary:read")
        and salary.employee_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Payslip not found.")
    employee = db.query(Employee).filter(Employee.id == salary.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Payslip not found.")
    values = {
        "Employee": f"{employee.first_name} {employee.last_name}",
        "Employee code": employee.employee_code,
        "Pay period": f"{salary.year}-{salary.month:02d}",
        "Basic salary": salary.basic_salary,
        "HRA": salary.hra,
        "Allowance": salary.allowance,
        "Bonus": salary.bonus,
        "Deduction": salary.deduction,
        "Tax": salary.tax,
        "Net salary": salary.net_salary,
        "Payment status": salary.payment_status,
        "Payment date": salary.payment_date or "Not paid",
    }
    rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(str(value))}</td></tr>"
        for label, value in values.items()
    )
    content = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Payslip</title><style>"
        "body{font:16px Arial,sans-serif;max-width:760px;margin:40px auto;color:#222}"
        "h1{border-bottom:2px solid #333;padding-bottom:12px}"
        "table{width:100%;border-collapse:collapse}th,td{text-align:left;"
        "padding:10px;border-bottom:1px solid #ddd}th{width:40%}"
        "@media print{body{margin:0 auto}}"
        "</style></head><body><h1>Employee Payslip</h1>"
        f"<table>{rows}</table></body></html>"
    )
    return HTMLResponse(
        content,
        headers={
            "Content-Disposition": (
                f'attachment; filename="payslip-{salary.year}-{salary.month:02d}-'
                f'{salary.employee_id}.html"'
            )
        },
    )


@router.post(
    "/payroll/generate",
    response_model=PayrollRunResponse,
    dependencies=[Depends(require_permission("payroll:generate"))],
)
def generate_payroll(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2200),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("payroll:generate")),
):
    return crud.generate_payroll(
        db,
        month=month,
        year=year,
        actor_id=current_user.id,
    )


@router.patch(
    "/{salary_id}",
    response_model=SalaryResponse,
    dependencies=[Depends(require_permission("payroll:generate"))],
)
def mark_salary_paid(
    salary_id: int,
    payload: SalaryUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission("payroll:generate")),
):
    updated_salary = crud.update_salary(
        db,
        salary_id,
        payload,
        actor_id=current_user.id,
    )
    if updated_salary is None:
        raise HTTPException(status_code=404, detail="Payroll entry not found.")
    return updated_salary


@router.get(
    "/{salary_id}",
    response_model=SalaryResponse,
    dependencies=[Depends(require_any_permission("salary:read", "payslip:read"))],
)
def get_salary(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("salary:read", "payslip:read")
    ),
):
    salary = crud.get_salary(db, salary_id)
    if salary is None:
        raise HTTPException(status_code=404, detail="Salary not found.")
    if not has_permission(db, current_user, "salary:read"):
        if salary.employee_id != current_user.id:
            raise HTTPException(status_code=404, detail="Salary not found.")
    return salary


@router.delete(
    "/{salary_id}",
    response_model=SalaryResponse,
    dependencies=[Depends(require_permission("salary:delete"))],
)
def delete_salary(
    salary_id: int,
    db: Session = Depends(get_db),
):
    deleted_salary = crud.delete_salary(db, salary_id)
    if deleted_salary is None:
        raise HTTPException(status_code=404, detail="Salary not found.")
    return deleted_salary
