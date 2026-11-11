import json
from datetime import date
from typing import Literal

from langchain_core.tools import tool
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.permissions import employee_scope_query, has_permission
from models.attendence import Attendance
from models.employee import Employee
from models.leave import Leave
from models.salary import Salary
from services import attendance as attendance_service

ReportType = Literal["dashboard", "attendance", "leave", "payroll"]


def create_report_tools(db: Session, employee_id: int):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise ValueError("Authenticated employee was not found.")
    if not (
        has_permission(db, employee, "ai:admin")
        and has_permission(db, employee, "report:read")
    ):
        return []

    @tool
    def get_report_data(
        report_type: ReportType,
        start_date: str,
        end_date: str,
    ) -> str:
        """Get permission-scoped aggregate data for an AI report summary.

        report_type is dashboard, attendance, leave, or payroll.
        Dates must use YYYY-MM-DD and cover no more than 366 days.
        Payroll data additionally requires salary:read.
        """
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            return json.dumps(
                {"error": "Dates must use YYYY-MM-DD format."}
            )
        if end < start:
            return json.dumps(
                {"error": "End date must be on or after start date."}
            )
        if (end - start).days > 365:
            return json.dumps(
                {"error": "Report date range cannot exceed 366 days."}
            )

        requested_types = (
            ["attendance", "leave", "payroll"]
            if report_type == "dashboard"
            else [report_type]
        )
        results: dict[str, object] = {
            "from": start.isoformat(),
            "to": end.isoformat(),
        }

        for requested_type in requested_types:
            if requested_type == "attendance":
                if not has_permission(db, employee, "attendance:read"):
                    results["attendance"] = {
                        "unavailable": "Attendance read permission is required."
                    }
                    continue
                report = attendance_service.build_attendance_report(
                    db,
                    employee,
                    start=start,
                    end=end,
                )
                results["attendance"] = {
                    "working_days": report["working_days"],
                    "employees_in_scope": len(report["employees"]),
                    "totals": report["totals"],
                }
                continue

            if requested_type == "leave":
                if not has_permission(db, employee, "leave:read"):
                    results["leave"] = {
                        "unavailable": "Leave read permission is required."
                    }
                    continue
                leave_rows = (
                    employee_scope_query(
                        db,
                        employee,
                        db.query(Leave),
                        Leave.employee_id,
                    )
                    .filter(
                        Leave.start_date <= end,
                        Leave.end_date >= start,
                    )
                    .with_entities(
                        Leave.status,
                        Leave.leave_type,
                        func.count(Leave.id),
                        func.coalesce(func.sum(Leave.total_days), 0),
                    )
                    .group_by(Leave.status, Leave.leave_type)
                    .all()
                )
                results["leave"] = {
                    "request_count": sum(row[2] for row in leave_rows),
                    "requested_days": sum(row[3] for row in leave_rows),
                    "by_status_and_type": [
                        {
                            "status": row[0],
                            "leave_type": row[1],
                            "requests": row[2],
                            "days": row[3],
                        }
                        for row in leave_rows
                    ],
                }
                continue

            if requested_type == "payroll":
                if not has_permission(db, employee, "salary:read"):
                    results["payroll"] = {
                        "unavailable": "Salary read permission is required."
                    }
                    continue
                payroll_query = employee_scope_query(
                    db,
                    employee,
                    db.query(Salary),
                    Salary.employee_id,
                )
                monthly_rows = (
                    payroll_query.filter(
                        (Salary.year * 100 + Salary.month)
                        >= start.year * 100 + start.month,
                        (Salary.year * 100 + Salary.month)
                        <= end.year * 100 + end.month,
                    )
                    .with_entities(
                        Salary.year,
                        Salary.month,
                        func.count(Salary.id),
                        func.coalesce(
                            func.sum(
                                Salary.basic_salary
                                + Salary.hra
                                + Salary.allowance
                                + Salary.bonus
                            ),
                            0,
                        ),
                        func.coalesce(
                            func.sum(Salary.deduction + Salary.tax),
                            0,
                        ),
                        func.coalesce(func.sum(Salary.net_salary), 0),
                    )
                    .group_by(Salary.year, Salary.month)
                    .order_by(Salary.year, Salary.month)
                    .all()
                )
                results["payroll"] = {
                    "entries": sum(row[2] for row in monthly_rows),
                    "gross_pay": round(sum(row[3] for row in monthly_rows), 2),
                    "deductions_and_tax": round(
                        sum(row[4] for row in monthly_rows),
                        2,
                    ),
                    "net_pay": round(sum(row[5] for row in monthly_rows), 2),
                    "monthly_totals": [
                        {
                            "year": row[0],
                            "month": row[1],
                            "entries": row[2],
                            "gross_pay": round(row[3], 2),
                            "deductions_and_tax": round(row[4], 2),
                            "net_pay": round(row[5], 2),
                        }
                        for row in monthly_rows
                    ],
                }

        return json.dumps(results)

    return [get_report_data]
