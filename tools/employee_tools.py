from langchain_core.tools import tool
from sqlalchemy.orm import Session

from models.employee import Employee
from crud import employee as crud


def create_employee_tools(
    db: Session,
    employee_id: int,
):
    """
    Create tools scoped to the authenticated employee.
    """

    @tool
    def get_my_profile() -> dict:
        """
        Get basic profile information for the authenticated employee.
        """

        employee = crud.get_employee(db, employee_id)

        if not employee:
            return {"error": "Employee profile not found."}

        return {
            "employee_id": employee.id,
            "employee_code": employee.employee_code,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "phone": employee.phone,
            "date_of_joining": employee.joining_date,
            "date_of_birth": employee.dob,
            "salary": employee.salary,
            "role": employee.role.name,
            "department": employee.department.name,
            "gender": employee.gender,
            "address": employee.address,
            "status": employee.status,
            "leave_balance": employee.leave_balance
        }

    return [
        get_my_profile,
    ]