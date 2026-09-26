from sqlalchemy.orm import Session
from models.salary import Salary
from schemas.salary import SalaryCreate, SalaryUpdate

def create_salary(db: Session, salary: SalaryCreate):
    db_salary = Salary(
        employee_id=salary.employee_id,
        month=salary.month,
        year=salary.year,
        basic_salary=salary.basic_salary,
        hra=salary.hra,
        allowance=salary.allowance,
        bonus=salary.bonus,
        deduction=salary.deduction,
        tax=salary.tax,
        net_salary=salary.net_salary
    )
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    return db_salary

def get_salaries(db: Session):
    return db.query(Salary).all()

def get_salary(db: Session, salary_id: int):
    return db.query(Salary).filter(Salary.id == salary_id).first()

def update_salary(db: Session, salary_id: int, salary: SalaryUpdate):
    db_salary = db.query(Salary).filter(Salary.id == salary_id).first()
    if not db_salary:
        return None

    for key, value in salary.dict(exclude_unset=True).items():
        setattr(db_salary, key, value)

    db.commit()
    db.refresh(db_salary)
    return db_salary

def delete_salary(db: Session, salary_id: int):
    db_salary = db.query(Salary).filter(Salary.id == salary_id).first()
    if not db_salary:
        return None

    db.delete(db_salary)
    db.commit()
    return db_salary

def get_my_salaries(db: Session, employee_id: int):
    return db.query(Salary).filter(Salary.employee_id == employee_id).all()


