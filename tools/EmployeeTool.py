import json
from typing import Annotated

from fastapi import HTTPException, status
from langchain.tools import tool
from langchain_core.tools import BaseTool
from pydantic import Field
from sqlalchemy.orm import Session

from auth.permissions import employee_scope_query, has_permission
from crud import employee as employee_crud
from models.employee import Employee


def _employee_summary(employee: Employee) -> dict[str, str | None]:
    return {
        "employee_code": employee.employee_code,
        "name": f"{employee.first_name} {employee.last_name}",
        "email": f"{employee.email}",
        "phone": f"{employee.phone}",
        "department": (
            employee.department.name if employee.department is not None else None
        ),
        "designation": (
            employee.designation.name if employee.designation is not None else None
        ),
        "date_of_joining": f"{employee.joining_date}",
        "Reporting Manager": (
            employee.reporting_manager.first_name if employee.reporting_manager is not None else None 
        ),
        "status": employee.status,
    }


class EmployeeTool:
    def __init__(self, db: Session, current_user: Employee):
        self.db = db
        self.current_user = current_user

    def as_tool(self) -> BaseTool:
        @tool(
            "get_employees",
            description=(
                "Get employees the signed-in user is authorized to view. "
                "Optional filters: name/code/email search and department ID."
            ),
        )
        def get_employees(
            search: Annotated[str | None, Field(max_length=100)] = None,
            department_id: Annotated[int | None, Field(ge=1)] = None,
            limit: Annotated[int, Field(ge=1, le=50)] = 20,
        ) -> str:
            """Return a JSON list of employee names and basic work details."""
            if not has_permission(self.db, self.current_user, "employee:read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view employees.",
                )

            query = employee_crud.employee_query(
                self.db,
                q=search,
                department_id=department_id,
            )
            query = employee_scope_query(
                self.db,
                self.current_user,
                query,
                Employee.id,
            )
            employees = (
                query.order_by(Employee.employee_code.asc())
                .limit(limit)
                .all()
            )
            return json.dumps([_employee_summary(employee) for employee in employees])

        return get_employees

    def get_employee_tool(self) -> BaseTool:
        @tool(
            "get_employee",
            description=(
                "Get one employee's basic work details by exact employee code, "
                "if the signed-in user is authorized to view that employee."
            ),
        )
        def get_employee(
            employee_code: Annotated[str, Field(min_length=3, max_length=20)],
        ) -> str:
            """Return basic work details for one employee."""
            if not has_permission(self.db, self.current_user, "employee:read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view employees.",
                )

            query = self.db.query(Employee).filter(
                Employee.employee_code == employee_code.strip()
            )
            query = employee_scope_query(
                self.db,
                self.current_user,
                query,
                Employee.id,
            )
            employee = query.first()
            if employee is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee not found.",
                )
            return json.dumps(_employee_summary(employee))

        return get_employee

    def as_tools(self) -> list[BaseTool]:
        return [self.as_tool(), self.get_employee_tool()]
