import csv
import io
import json
import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import (
    employee_scope_query,
    has_permission,
    require_any_permission,
    require_permission,
)
from database import get_db
from models.attendence import Attendance
from models.department import Department
from models.employee import Employee
from models.leave import Leave
from models.salary import Salary
from services import attendance as attendance_service

router = APIRouter()

ReportType = Literal[
    "employees",
    "attendance",
    "leaves",
    "payroll",
    "departments",
    "attrition",
]


def build_analytics(
    db: Session,
    user: Employee,
    *,
    start: date,
    end: date,
    department_id: int | None = None,
) -> dict[str, object]:
    if end < start:
        raise HTTPException(
            status_code=422,
            detail="'to' date cannot be before 'from' date.",
        )

    employee_query = employee_scope_query(
        db,
        user,
        db.query(Employee),
        Employee.id,
    )
    if department_id is not None:
        employee_query = employee_query.filter(
            Employee.department_id == department_id
        )

    employees = employee_query.order_by(Employee.id).all()
    employee_ids = {employee.id for employee in employees}
    active_employees = [employee for employee in employees if employee.is_active]
    hires = [
        employee
        for employee in employees
        if employee.joining_date is not None
        and start <= employee.joining_date <= end
    ]
    exits = [
        employee
        for employee in employees
        if not employee.is_active
        and employee.exit_date is not None
        and start <= employee.exit_date <= end
    ]
    opening_headcount = sum(
        employee.joining_date is not None
        and employee.joining_date <= start
        and (employee.exit_date is None or employee.exit_date >= start)
        for employee in employees
    )

    result: dict[str, object] = {
        "from": start,
        "to": end,
        "department_id": department_id,
    }
    if has_permission(db, user, "employee:read"):
        result["employees"] = {
            "total_in_scope": len(employees),
            "active": len(active_employees),
            "inactive": len(employees) - len(active_employees),
            "hires_in_period": len(hires),
            "active_employee_details": [
                {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "department_id": employee.department_id,
                    "joining_date": employee.joining_date,
                }
                for employee in active_employees
            ],
        }
        result["attrition"] = {
            "opening_headcount": opening_headcount,
            "exits_in_period": len(exits),
            "attrition_rate_percent": round(
                len(exits) / opening_headcount * 100,
                2,
            )
            if opening_headcount
            else 0.0,
            "exits": [
                {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "department_id": employee.department_id,
                    "exit_date": employee.exit_date,
                    "exit_reason": employee.exit_reason,
                }
                for employee in exits
            ],
        }

    if has_permission(db, user, "attendance:read"):
        attendance_report = attendance_service.build_attendance_report(
            db,
            user,
            start=start,
            end=end,
            department_id=department_id,
        )
        result["attendance"] = {
            "from": attendance_report["from"],
            "to": attendance_report["to"],
            "department_id": attendance_report["department_id"],
            "working_days": attendance_report["working_days"],
            "totals": attendance_report["totals"],
            "employees": attendance_report["employees"],
        }

    if has_permission(db, user, "leave:read"):
        leave_query = db.query(Leave).filter(
            Leave.employee_id.in_(employee_ids) if employee_ids else False,
            Leave.start_date <= end,
            Leave.end_date >= start,
        )
        leaves = leave_query.order_by(Leave.start_date, Leave.id).all()
        leave_totals = {
            "requests": len(leaves),
            "requested_days": sum(
                (min(item.end_date, end) - max(item.start_date, start)).days + 1
                for item in leaves
            ),
            "pending": sum(item.status == "Pending" for item in leaves),
            "approved": sum(item.status == "Approved" for item in leaves),
            "rejected": sum(item.status == "Rejected" for item in leaves),
            "cancelled": sum(item.status == "Cancelled" for item in leaves),
        }
        result["leaves"] = {
            "totals": leave_totals,
            "by_type": _group_counts(
                (
                    item.leave_type,
                    (min(item.end_date, end) - max(item.start_date, start)).days
                    + 1,
                )
                for item in leaves
            ),
            "requests": [
                {
                    "employee_id": item.employee_id,
                    "leave_type": item.leave_type,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "days": item.total_days,
                    "status": item.status,
                }
                for item in leaves
            ],
        }

    if has_permission(db, user, "salary:read"):
        payroll_query = db.query(Salary).filter(
            Salary.year * 100 + Salary.month
            >= start.year * 100 + start.month,
            Salary.year * 100 + Salary.month <= end.year * 100 + end.month,
        )
        if department_id is not None:
            payroll_query = payroll_query.join(
                Employee,
                Employee.id == Salary.employee_id,
            ).filter(Employee.department_id == department_id)
        salaries = payroll_query.order_by(
            Salary.year,
            Salary.month,
            Salary.employee_id,
        ).all()
        result["payroll"] = {
            "payroll_entries": len(salaries),
            "gross_pay": round(
                sum(
                    item.basic_salary
                    + item.hra
                    + item.allowance
                    + item.bonus
                    for item in salaries
                ),
                2,
            ),
            "deductions_and_tax": round(
                sum(item.deduction + item.tax for item in salaries),
                2,
            ),
            "net_pay": round(sum(item.net_salary for item in salaries), 2),
            "paid_entries": sum(item.payment_status == "Paid" for item in salaries),
            "pending_entries": sum(
                item.payment_status == "Pending" for item in salaries
            ),
            "monthly_totals": _group_payroll(salaries),
        }

    if has_permission(db, user, "employee:read"):
        scoped_department_ids = {
            employee.department_id
            for employee in employees
            if employee.department_id is not None
        }
        departments = (
            db.query(Department.id, Department.name)
            .filter(Department.id.in_(scoped_department_ids))
            .order_by(Department.name)
            .all()
            if scoped_department_ids
            else []
        )
        attendance_by_employee: dict[int, int] = {}
        if has_permission(db, user, "attendance:read") and employee_ids:
            attendance_counts = db.query(
                Attendance.employee_id,
                func.count(Attendance.id),
            ).filter(
                Attendance.employee_id.in_(employee_ids),
                Attendance.attendance_date >= start,
                Attendance.attendance_date <= end,
            ).group_by(Attendance.employee_id).all()
            attendance_by_employee = dict(attendance_counts)

        leave_by_employee: dict[int, int] = {}
        if has_permission(db, user, "leave:read") and employee_ids:
            approved_leave_rows = db.query(Leave).filter(
                Leave.employee_id.in_(employee_ids),
                Leave.status == "Approved",
                Leave.start_date <= end,
                Leave.end_date >= start,
            ).all()
            for leave in approved_leave_rows:
                employee_id = leave.employee_id
                days = (
                    min(leave.end_date, end) - max(leave.start_date, start)
                ).days + 1
                leave_by_employee[employee_id] = (
                    leave_by_employee.get(employee_id, 0) + days
                )
        payroll_by_department: dict[int, dict[str, int | float]] = {}
        if has_permission(db, user, "salary:read") and employee_ids:
            scoped_salaries = db.query(Salary).filter(
                Salary.employee_id.in_(employee_ids),
                Salary.year * 100 + Salary.month
                >= start.year * 100 + start.month,
                Salary.year * 100 + Salary.month <= end.year * 100 + end.month,
            ).all()
            employee_departments = {
                employee.id: employee.department_id for employee in employees
            }
            for salary in scoped_salaries:
                salary_department_id = employee_departments.get(salary.employee_id)
                if salary_department_id is None:
                    continue
                totals = payroll_by_department.setdefault(
                    salary_department_id,
                    {"payroll_entries": 0, "net_pay": 0.0},
                )
                totals["payroll_entries"] += 1
                totals["net_pay"] += salary.net_salary
        department_rows = []
        for department, name in departments:
            scoped = [
                employee
                for employee in employees
                if employee.department_id == department
            ]
            department_rows.append(
                {
                    "department_id": department,
                    "department": name,
                    "employees": len(scoped),
                    "active_employees": sum(item.is_active for item in scoped),
                    "hires_in_period": sum(item in hires for item in scoped),
                    "exits_in_period": sum(item in exits for item in scoped),
                    "attendance_records": sum(
                        attendance_by_employee.get(item.id, 0)
                        for item in scoped
                    ),
                    "approved_leave_days": sum(
                        leave_by_employee.get(item.id, 0) for item in scoped
                    ),
                    "payroll_entries": payroll_by_department.get(
                        department,
                        {},
                    ).get("payroll_entries", 0),
                    "payroll_net_pay": round(
                        payroll_by_department.get(department, {}).get(
                            "net_pay",
                            0.0,
                        ),
                        2,
                    ),
                }
            )
        result["departments"] = department_rows

    return result


def _group_counts(items) -> list[dict[str, int | str]]:
    grouped: dict[str, int] = {}
    for label, amount in items:
        grouped[label] = grouped.get(label, 0) + amount
    return [
        {"category": category, "days": amount}
        for category, amount in sorted(grouped.items())
    ]


def _group_payroll(salaries: list[Salary]) -> list[dict[str, int | float]]:
    grouped: dict[tuple[int, int], dict[str, int | float]] = {}
    for salary in salaries:
        key = (salary.year, salary.month)
        totals = grouped.setdefault(
            key,
            {
                "year": salary.year,
                "month": salary.month,
                "entries": 0,
                "gross_pay": 0.0,
                "net_pay": 0.0,
            },
        )
        totals["entries"] += 1
        totals["gross_pay"] += (
            salary.basic_salary + salary.hra + salary.allowance + salary.bonus
        )
        totals["net_pay"] += salary.net_salary
    return [
        {
            **totals,
            "gross_pay": round(totals["gross_pay"], 2),
            "net_pay": round(totals["net_pay"], 2),
        }
        for _, totals in sorted(grouped.items())
    ]


def _report_rows(
    report_type: ReportType,
    analytics: dict[str, object],
) -> list[dict[str, object]]:
    section = analytics.get(report_type)
    if section is None:
        raise HTTPException(
            status_code=403,
            detail=f"You don't have permission to export {report_type} reports.",
        )
    if report_type == "employees":
        return list(section["active_employee_details"])
    if report_type == "attrition":
        return list(section["exits"])
    if report_type == "attendance":
        return list(section["employees"])
    if report_type == "leaves":
        return list(section["requests"])
    if report_type == "payroll":
        return list(section["monthly_totals"])
    return list(section)


def _csv_content(rows: list[dict[str, object]], report_type: ReportType) -> str:
    output = io.StringIO(newline="")
    empty_columns = {
        "employees": [
            "employee_id",
            "employee_code",
            "name",
            "department_id",
            "joining_date",
        ],
        "attendance": [
            "employee_id",
            "employee_code",
            "name",
            "department_id",
            "present_days",
            "absent_days",
            "late_days",
            "wfh_days",
            "office_days",
            "overtime_hours",
            "unpaid_days",
        ],
        "leaves": [
            "employee_id",
            "leave_type",
            "start_date",
            "end_date",
            "days",
            "status",
        ],
        "payroll": ["year", "month", "entries", "gross_pay", "net_pay"],
        "departments": [
            "department_id",
            "department",
            "employees",
            "active_employees",
            "hires_in_period",
            "exits_in_period",
            "attendance_records",
            "approved_leave_days",
            "payroll_entries",
            "payroll_net_pay",
        ],
        "attrition": [
            "employee_id",
            "employee_code",
            "name",
            "department_id",
            "exit_date",
            "exit_reason",
        ],
    }
    columns = (
        list(dict.fromkeys(key for row in rows for key in row))
        if rows
        else empty_columns[report_type]
    )
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, default=str)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
        )
    return output.getvalue()


def _pdf_content(title: str, rows: list[dict[str, object]]) -> bytes:
    lines = [title, ""]
    if not rows:
        lines.append("No records found for the selected period.")
    else:
        for row in rows:
            lines.append(
                " | ".join(
                    f"{key}: {json.dumps(value, default=str) if isinstance(value, (dict, list)) else value}"
                    for key, value in row.items()
                )
            )
    wrapped: list[str] = []
    for line in lines:
        safe_line = line.encode("cp1252", errors="replace").decode("cp1252")
        wrapped.extend(
            safe_line[offset : offset + 95]
            for offset in range(0, max(len(safe_line), 1), 95)
        )
    page_chunks = [wrapped[index : index + 48] for index in range(0, len(wrapped), 48)]

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(
            f"{4 + 2 * index} 0 R".encode("ascii")
            for index in range(len(page_chunks))
        )
        + f"] /Count {len(page_chunks)} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_index, chunk in enumerate(page_chunks):
        page_object_id = 4 + 2 * page_index
        content_object_id = page_object_id + 1
        commands = ["BT", "/F1 9 Tf", "45 750 Td", "12 TL"]
        for line in chunk:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("cp1252", errors="replace")
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {content_object_id} 0 R >>"
                ).encode("ascii"),
                (
                    f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
                    + stream
                    + b"\nendstream"
                ),
            ]
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, content in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(content)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


@router.get(
    "/analytics",
    dependencies=[
        Depends(require_any_permission("report:read", "report:team:read"))
    ],
)
def analytics_report(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    department_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("report:read", "report:team:read")
    ),
):
    return build_analytics(
        db,
        current_user,
        start=from_,
        end=to,
        department_id=department_id,
    )


@router.get(
    "/{report_type}/export",
    dependencies=[
        Depends(require_any_permission("report:read", "report:team:read"))
    ],
)
def export_report(
    report_type: ReportType,
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    department_id: int | None = Query(default=None, ge=1),
    file_format: Literal["csv", "pdf"] = Query(default="csv", alias="format"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(
        require_any_permission("report:read", "report:team:read")
    ),
):
    analytics = build_analytics(
        db,
        current_user,
        start=from_,
        end=to,
        department_id=department_id,
    )
    rows = _report_rows(report_type, analytics)
    filename = f"{report_type}-report-{from_.isoformat()}-{to.isoformat()}"
    if file_format == "csv":
        content = _csv_content(rows, report_type).encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
        filename += ".csv"
    else:
        content = _pdf_content(f"{report_type.title()} Report", rows)
        media_type = "application/pdf"
        filename += ".pdf"
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "-", filename)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


@router.get(
    "/attendance",
    dependencies=[Depends(require_permission("report:read"))],
)
def attendance_report(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    department_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return attendance_service.build_attendance_report(
        db,
        current_user,
        start=from_,
        end=to,
        department_id=department_id,
    )
