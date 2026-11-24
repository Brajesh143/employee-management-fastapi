import json
import secrets
from datetime import date
from typing import Annotated, Any

from fastapi import HTTPException, status
from langchain.tools import tool
from langchain_core.tools import BaseTool
from pydantic import Field
from sqlalchemy.orm import Session

from auth.permissions import (
    employee_scope_query,
    ensure_role_assignment_allowed,
    has_permission,
)
from crud import employee as employee_crud
from models.employee import Employee
from schemas.employee import EmployeeCreate


def _employee_summary(employee: Employee) -> dict[str, Any]:
    summary = {
        column.key: getattr(employee, column.key)
        for column in Employee.__table__.columns
        if column.key != "password_hash"
    }
    summary.update(
        {
            "name": f"{employee.first_name} {employee.last_name}",
            "department": (
                employee.department.name if employee.department is not None else None
            ),
            "role": employee.role.name if employee.role is not None else None,
            "designation": (
                employee.designation.name if employee.designation is not None else None
            ),
            "shift": employee.shift.name if employee.shift is not None else None,
            "reporting manager": (
                employee.reporting_manager.first_name
                if employee.reporting_manager_id is not None
                else None
            ),
            "is_active": employee.is_active,
        }
    )
    return summary


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
            return json.dumps(
                [_employee_summary(employee) for employee in employees],
                default=str,
            )

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
            return json.dumps(_employee_summary(employee), default=str)

        return get_employee

    def create_employee_tool(self) -> BaseTool:
        @tool(
            "create_employee",
            description=(
                "Create an employee after the user explicitly confirms the "
                "complete employee details. Call first with confirmed=false "
                "to prepare a preview. After showing the preview and receiving "
                "confirmation, call again with the same details and confirmed=true. "
                "A temporary password is generated and returned once after creation."
            ),
        )
        def create_employee(
            employee_code: Annotated[str, Field(min_length=3, max_length=20)],
            first_name: Annotated[str, Field(min_length=1, max_length=50)],
            last_name: Annotated[str, Field(min_length=1, max_length=50)],
            email: Annotated[str, Field(min_length=5, max_length=100)],
            phone: Annotated[str | None, Field(max_length=15)] = None,
            gender: Annotated[str | None, Field(max_length=10)] = None,
            dob: date | None = None,
            joining_date: date | None = None,
            department_id: int | None = None,
            designation_id: int | None = None,
            role_id: int | None = None,
            reporting_manager_id: int | None = None,
            shift_id: int | None = None,
            address: str | None = None,
            salary: float | None = None,
            profile_image: str | None = None,
            employee_status: Annotated[str | None, Field(max_length=20)] = None,
            confirmed: bool = False,
        ) -> str:
            """Prepare or create an employee after explicit user confirmation."""
            if not has_permission(self.db, self.current_user, "employee:create"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to create employees.",
                )

            temporary_password = secrets.token_urlsafe(24)
            employee_data = EmployeeCreate(
                employee_code=employee_code,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                gender=gender,
                dob=dob,
                joining_date=joining_date,
                department_id=department_id,
                designation_id=designation_id,
                role_id=role_id,
                reporting_manager_id=reporting_manager_id,
                shift_id=shift_id,
                address=address,
                salary=salary,
                profile_image=profile_image,
                status=employee_status,
                password=temporary_password,
            )

            if not confirmed:
                return json.dumps(
                    {
                        "status": "confirmation_required",
                        "employee": employee_data.model_dump(
                            exclude={"password", "is_verified"},
                            mode="json",
                        ),
                        "message": (
                            "No employee was created. Show these details to the "
                            "user and ask for confirmation before creating."
                        ),
                    }
                )

            ensure_role_assignment_allowed(
                self.db,
                self.current_user,
                employee_data.role_id,
            )
            try:
                employee = employee_crud.create_employee(
                    self.db,
                    employee_data,
                    actor_id=self.current_user.id,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

            return json.dumps(
                {
                    "status": "created",
                    "employee": _employee_summary(employee),
                    "temporary_password": temporary_password,
                    "message": (
                        "Share this temporary password with the employee "
                        "securely. It will not be shown again."
                    ),
                },
                default=str,
            )

        return create_employee

    def as_tools(self) -> list[BaseTool]:
        return [
            self.as_tool(),
            self.get_employee_tool(),
            self.create_employee_tool(),
        ]
