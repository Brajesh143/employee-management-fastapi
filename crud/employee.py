from sqlalchemy.orm import Session
from models.employee import Employee
from schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from auth.hashing import Hash


def create_employee(db: Session, employee: EmployeeCreate):
    db_employee = Employee(
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        phone=employee.phone,
        gender=employee.gender,
        dob=employee.dob,
        joining_date=employee.joining_date,
        department_id=employee.department_id,
        role_id=employee.role_id,
        address=employee.address,
        salary=employee.salary,
        profile_image=employee.profile_image,
        status=employee.status,
        password_hash=Hash.hash_password(employee.password),
    )

    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    return db_employee

def get_employees(db: Session):
    return db.query(Employee).all()

def get_employee(db: Session, employee_id: int):
    return (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .first()
    )

def update_employee(employee_id: int, employee: EmployeeUpdate, db: Session):
    db_employee = get_employee(db, employee_id)

    if not db_employee:
        return None

    update_data = employee.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_employee, key, value)

    db.commit()
    db.refresh(db_employee)

    return db_employee

def delete_employee(db: Session, employee_id: int):
    db_employee = get_employee(db, employee_id)

    if not db_employee:
        return None

    db.delete(db_employee)
    db.commit()

    return db_employee

