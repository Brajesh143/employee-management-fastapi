from datetime import date
from langchain.tools import tool

from models.leave import Leave
from models.employee import Employee


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

            if end < start:
                return "Error: End date cannot be before start date."

            employee = (
                db.query(Employee)
                .filter(Employee.id == employee_id)
                .first()
            )

            if not employee:
                return "Error: Employee not found."

            leave = Leave(
                employee_id=employee_id,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                reason=reason,
                status="Pending",
            )

            db.add(leave)
            db.commit()
            db.refresh(leave)

            return (
                f"Leave request created successfully. "
                f"Request ID: {leave.id}. "
                f"Status: Pending."
            )

        except Exception:
            db.rollback()
            return "Error: Unable to create the leave request."

    return [create_leave_request]