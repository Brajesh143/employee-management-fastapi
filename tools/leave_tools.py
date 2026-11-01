from datetime import date
from langchain.tools import tool
from fastapi import HTTPException
from pydantic import ValidationError

from crud.leave import create_leave
from models.employee import Employee
from schemas.leave import LeaveCreate


def create_leave_tools(db, employee_id: int):

    @tool
    def create_leave_request(
        leave_type: str,
        start_date: str,
        end_date: str,
        reason: str,
    ) -> str:
        """
        Create a leave request for the currently authenticated employee.

        Use this tool when the employee explicitly asks to apply
        for or submit a leave request.
        """

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            request = LeaveCreate(
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                reason=reason,
            )

            employee = (
                db.query(Employee)
                .filter(Employee.id == employee_id)
                .first()
            )

            if not employee:
                return "Error: Employee not found."

            leave = create_leave(
                db,
                request,
                employee=employee,
                actor_id=employee_id,
            )

            return (
                f"Leave request created successfully. "
                f"Request ID: {leave.id}. "
                f"Status: Pending."
            )

        except (ValueError, ValidationError) as exc:
            return f"Error: {exc}"
        except HTTPException as exc:
            return f"Error: {exc.detail}"
        except Exception:
            db.rollback()
            raise

    return [create_leave_request]