import json
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import HTTPException, status
from langchain.tools import tool
from langchain_core.tools import BaseTool
from pydantic import Field
from sqlalchemy.orm import Session

from auth.permissions import employee_scope_query, has_permission
from models.attendence import Attendance
from models.employee import Employee
from services import attendance as attendance_service


def _attendance_summary(attendance: Attendance) -> dict[str, Any]:
    return {
        column.key: getattr(attendance, column.key)
        for column in Attendance.__table__.columns
    }


class AttendanceTool:
    def __init__(self, db: Session, current_user: Employee):
        self.db = db
        self.current_user = current_user

    def as_tools(self) -> list[BaseTool]:
        @tool(
            "check_in",
            description=(
                "Record the signed-in employee's check-in for today. "
                "Use only when the user explicitly asks to check in. "
                "WFH check-in requires an approved WFH request or an enabled policy."
            ),
        )
        def check_in(
            work_mode: Literal["office", "wfh"] = "office",
            notes: Annotated[str | None, Field(max_length=500)] = None,
        ) -> str:
            """Record a check-in for the authenticated employee."""
            if not has_permission(self.db, self.current_user, "attendance:create"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to record attendance.",
                )

            record = attendance_service.check_in(
                self.db,
                self.current_user,
                work_mode=work_mode,
                source="chatbot",
                notes=notes,
            )
            return json.dumps(_attendance_summary(record), default=str)

        @tool(
            "check_out",
            description=(
                "Record the signed-in employee's check-out for today. "
                "Use only when the user explicitly asks to check out."
            ),
        )
        def check_out(
            notes: Annotated[str | None, Field(max_length=500)] = None,
        ) -> str:
            """Record a check-out for the authenticated employee."""
            if not has_permission(self.db, self.current_user, "attendance:create"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to record attendance.",
                )

            record = attendance_service.check_out(
                self.db,
                self.current_user,
                notes=notes,
            )
            return json.dumps(_attendance_summary(record), default=str)

        @tool(
            "get_today_attendance",
            description="Get the signed-in employee's attendance record for today.",
        )
        def get_today_attendance() -> str:
            """Return today's attendance record, if one exists."""
            if not has_permission(self.db, self.current_user, "attendance:read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view attendance.",
                )

            today = attendance_service.current_datetime().date()
            record = (
                self.db.query(Attendance)
                .filter(
                    Attendance.employee_id == self.current_user.id,
                    Attendance.attendance_date == today,
                )
                .first()
            )
            return json.dumps(
                _attendance_summary(record) if record is not None else None,
                default=str,
            )

        @tool(
            "get_attendance_history",
            description=(
                "Get attendance records visible to the signed-in employee. "
                "Defaults to the signed-in employee; other employee IDs are "
                "restricted by their attendance access scope."
            ),
        )
        def get_attendance_history(
            start_date: date | None = None,
            end_date: date | None = None,
            employee_id: Annotated[int | None, Field(ge=1)] = None,
            limit: Annotated[int, Field(ge=1, le=100)] = 50,
        ) -> str:
            """Return visible attendance records within an optional date range."""
            if not has_permission(self.db, self.current_user, "attendance:read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view attendance.",
                )
            if (
                start_date is not None
                and end_date is not None
                and start_date > end_date
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="start_date must be on or before end_date.",
                )

            query = employee_scope_query(
                self.db,
                self.current_user,
                self.db.query(Attendance),
                Attendance.employee_id,
            )
            query = query.filter(
                Attendance.employee_id
                == (employee_id if employee_id is not None else self.current_user.id)
            )
            if start_date is not None:
                query = query.filter(Attendance.attendance_date >= start_date)
            if end_date is not None:
                query = query.filter(Attendance.attendance_date <= end_date)

            records = (
                query.order_by(Attendance.attendance_date.desc())
                .limit(limit)
                .all()
            )
            return json.dumps(
                [_attendance_summary(record) for record in records],
                default=str,
            )

        return [check_in, check_out, get_today_attendance, get_attendance_history]
