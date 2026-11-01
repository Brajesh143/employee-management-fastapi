from calendar import monthrange
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.employee import Employee
from models.salary import Salary
from models.salary_structure import SalaryStructure
from schemas.salary import SalaryCreate, SalaryStructureCreate, SalaryUpdate
from services.audit import write_audit_log


def _salary_snapshot(salary: Salary) -> dict[str, int | float | str | None]:
    return {
        "id": salary.id,
        "employee_id": salary.employee_id,
        "month": salary.month,
        "year": salary.year,
        "net_salary": salary.net_salary,
        "payment_status": salary.payment_status,
        "payment_date": str(salary.payment_date) if salary.payment_date else None,
    }


def create_salary_structure(
    db: Session,
    payload: SalaryStructureCreate,
    *,
    actor_id: int,
) -> SalaryStructure:
    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=404, detail="Active employee not found.")
    existing = (
        db.query(SalaryStructure)
        .filter(
            SalaryStructure.employee_id == payload.employee_id,
            SalaryStructure.effective_from == payload.effective_from,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A salary structure already exists for this employee and effective date.",
        )
    structure = SalaryStructure(**payload.model_dump())
    db.add(structure)
    db.flush()
    write_audit_log(
        db,
        actor_id=actor_id,
        action="salary.structure.create",
        resource_type="salary_structure",
        resource_id=structure.id,
        after={
            "employee_id": structure.employee_id,
            "basic_salary": structure.basic_salary,
            "hra": structure.hra,
            "allowance": structure.allowance,
            "recurring_deduction": structure.recurring_deduction,
            "tax_rate": structure.tax_rate,
            "effective_from": structure.effective_from,
        },
    )
    db.commit()
    db.refresh(structure)
    return structure


def create_salary(
    db: Session,
    payload: SalaryCreate,
    *,
    actor_id: int,
) -> Salary:
    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if (
        db.query(Salary)
        .filter(
            Salary.employee_id == payload.employee_id,
            Salary.month == payload.month,
            Salary.year == payload.year,
        )
        .first()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll already exists for this employee and month.",
        )
    gross = (
        payload.basic_salary
        + payload.hra
        + payload.allowance
        + payload.bonus
    )
    db_salary = Salary(
        **payload.model_dump(exclude={"payment_status", "payment_date"}),
        net_salary=round(gross - payload.deduction - payload.tax, 2),
        payment_status=payload.payment_status,
        payment_date=payload.payment_date,
    )
    db.add(db_salary)
    db.flush()
    write_audit_log(
        db,
        actor_id=actor_id,
        action="payroll.salary.create",
        resource_type="salary",
        resource_id=db_salary.id,
        after=_salary_snapshot(db_salary),
    )
    db.commit()
    db.refresh(db_salary)
    return db_salary


def get_salary_structures(
    db: Session,
    *,
    employee_id: int | None = None,
) -> list[SalaryStructure]:
    query = db.query(SalaryStructure)
    if employee_id is not None:
        query = query.filter(SalaryStructure.employee_id == employee_id)
    return query.order_by(
        SalaryStructure.employee_id,
        SalaryStructure.effective_from.desc(),
    ).all()


def generate_payroll(
    db: Session,
    *,
    month: int,
    year: int,
    actor_id: int,
) -> dict[str, object]:
    if month < 1 or month > 12:
        raise HTTPException(status_code=422, detail="Month must be between 1 and 12.")
    if year < 2000 or year > 2200:
        raise HTTPException(status_code=422, detail="Year must be between 2000 and 2200.")

    payroll_date = date(year, month, monthrange(year, month)[1])
    employees = (
        db.query(Employee)
        .filter(Employee.is_active.is_(True))
        .order_by(Employee.id)
        .all()
    )
    generated: list[Salary] = []
    skipped = 0
    for employee in employees:
        existing = (
            db.query(Salary)
            .filter(
                Salary.employee_id == employee.id,
                Salary.month == month,
                Salary.year == year,
            )
            .first()
        )
        if existing is not None:
            skipped += 1
            continue
        structure = (
            db.query(SalaryStructure)
            .filter(
                SalaryStructure.employee_id == employee.id,
                SalaryStructure.effective_from <= payroll_date,
            )
            .order_by(SalaryStructure.effective_from.desc())
            .first()
        )
        if structure is None:
            skipped += 1
            continue

        gross = structure.basic_salary + structure.hra + structure.allowance
        tax = round(gross * structure.tax_rate / 100, 2)
        total_deduction = structure.recurring_deduction
        salary = Salary(
            employee_id=employee.id,
            month=month,
            year=year,
            basic_salary=structure.basic_salary,
            hra=structure.hra,
            allowance=structure.allowance,
            bonus=0,
            deduction=total_deduction,
            tax=tax,
            net_salary=round(gross - total_deduction - tax, 2),
            payment_status="Pending",
        )
        db.add(salary)
        generated.append(salary)

    db.flush()
    for salary in generated:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="payroll.salary.generate",
            resource_type="salary",
            resource_id=salary.id,
            after=_salary_snapshot(salary),
        )
    db.commit()
    for salary in generated:
        db.refresh(salary)
    return {
        "month": month,
        "year": year,
        "generated_count": len(generated),
        "skipped_count": skipped,
        "total_net_pay": round(sum(item.net_salary for item in generated), 2),
        "salaries": generated,
    }


def get_salaries(
    db: Session,
    *,
    employee_id: int | None = None,
    month: int | None = None,
    year: int | None = None,
) -> list[Salary]:
    query = db.query(Salary)
    if employee_id is not None:
        query = query.filter(Salary.employee_id == employee_id)
    if month is not None:
        query = query.filter(Salary.month == month)
    if year is not None:
        query = query.filter(Salary.year == year)
    return query.order_by(Salary.year.desc(), Salary.month.desc(), Salary.id.desc()).all()


def get_salary(db: Session, salary_id: int) -> Salary | None:
    return db.query(Salary).filter(Salary.id == salary_id).first()


def update_salary(
    db: Session,
    salary_id: int,
    salary: SalaryUpdate,
    *,
    actor_id: int,
) -> Salary | None:
    db_salary = get_salary(db, salary_id)
    if db_salary is None:
        return None
    if db_salary.payment_status == "Paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This payroll entry is already paid.",
        )
    before = _salary_snapshot(db_salary)
    db_salary.payment_status = "Paid"
    db_salary.payment_date = salary.payment_date
    write_audit_log(
        db,
        actor_id=actor_id,
        action="payroll.salary.paid",
        resource_type="salary",
        resource_id=db_salary.id,
        before=before,
        after=_salary_snapshot(db_salary),
    )
    db.commit()
    db.refresh(db_salary)
    return db_salary


def get_salary_by_employee(
    db: Session,
    employee_id: int,
    *,
    year: int | None = None,
    month: int | None = None,
) -> list[Salary]:
    return get_salaries(
        db,
        employee_id=employee_id,
        year=year,
        month=month,
    )


def delete_salary(db: Session, salary_id: int) -> Salary | None:
    db_salary = get_salary(db, salary_id)
    if db_salary is None:
        return None
    if db_salary.payment_status == "Paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Paid payroll entries cannot be deleted.",
        )
    db.delete(db_salary)
    db.commit()
    return db_salary
