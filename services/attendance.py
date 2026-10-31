from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.attendance_correction import AttendanceCorrection
from models.attendance_policy import AttendancePolicy
from models.attendence import Attendance
from models.employee import Employee
from models.holiday import Holiday
from models.leave import Leave
from models.shift import Shift
from models.wfh_request import WfhRequest
from services.audit import write_audit_log
from services.notifications import notify

ORG_ROLES = {"Super Admin", "Admin", "Human Resource"}
WORK_MODES = {"office", "wfh"}


def current_datetime() -> datetime:
    return datetime.now()


def attendance_snapshot(record: Attendance) -> dict:
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "attendance_date": str(record.attendance_date),
        "check_in": str(record.check_in) if record.check_in else None,
        "check_out": str(record.check_out) if record.check_out else None,
        "working_hours": record.working_hours,
        "overtime_hours": record.overtime_hours,
        "late_minutes": record.late_minutes,
        "early_leave_minutes": record.early_leave_minutes,
        "status": record.status,
        "work_mode": record.work_mode,
    }


def get_permission_names(db: Session, user: Employee) -> set[str]:
    from models.permission import Permission
    from models.role_permission import RolePermission

    if user.role_id is None:
        return set()

    rows = (
        db.query(Permission.name)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .filter(RolePermission.role_id == user.role_id)
        .all()
    )
    return {name for (name,) in rows}


def role_name(user: Employee) -> str:
    return getattr(user.role, "name", "") or ""


def is_org_admin(user: Employee) -> bool:
    return role_name(user) in ORG_ROLES


def can_review_employee(reviewer: Employee, employee: Employee) -> bool:
    if reviewer.id == employee.reporting_manager_id:
        return True
    return is_org_admin(reviewer)


def get_or_create_default_shift(db: Session) -> Shift:
    shift = db.query(Shift).filter(Shift.is_default.is_(True)).first()
    if shift:
        return shift

    shift = Shift(
        name="General Shift",
        start_time=time(9, 0),
        end_time=time(18, 0),
        grace_minutes=30,
        unpaid_break_minutes=60,
        is_default=True,
        is_active=True,
    )
    db.add(shift)
    db.flush()
    return shift


def get_or_create_policy(db: Session) -> AttendancePolicy:
    policy = db.query(AttendancePolicy).first()
    if policy:
        return policy

    policy = AttendancePolicy(
        allow_direct_wfh=False,
        weekend_days="5,6",
    )
    db.add(policy)
    db.flush()
    return policy


def resolve_shift(db: Session, employee: Employee) -> Shift:
    if employee.shift_id:
        shift = db.query(Shift).filter(Shift.id == employee.shift_id).first()
        if shift:
            return shift
    return get_or_create_default_shift(db)


def parse_weekend_days(policy: AttendancePolicy) -> set[int]:
    if not policy.weekend_days:
        return {5, 6}
    return {
        int(part.strip())
        for part in policy.weekend_days.split(",")
        if part.strip().isdigit()
    }


def expected_shift_hours(shift: Shift) -> float:
    start = datetime.combine(date.today(), shift.start_time)
    end = datetime.combine(date.today(), shift.end_time)
    if end <= start:
        end += timedelta(days=1)
    raw = (end - start).total_seconds() / 3600
    break_hours = (shift.unpaid_break_minutes or 0) / 60
    return max(round(raw - break_hours, 2), 0)


def compute_metrics(
    *,
    check_in: datetime,
    check_out: datetime | None,
    shift: Shift,
) -> dict:
    shift_start = datetime.combine(check_in.date(), shift.start_time)
    grace_deadline = shift_start + timedelta(minutes=shift.grace_minutes or 0)

    late_minutes = 0
    if check_in > grace_deadline:
        late_minutes = int((check_in - shift_start).total_seconds() // 60)

    working_hours = 0.0
    overtime_hours = 0.0
    early_leave_minutes = 0
    status = "Late" if late_minutes > 0 else "Present"

    if check_out:
        if check_out < check_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Check-out cannot be before check-in.",
            )

        raw_hours = (check_out - check_in).total_seconds() / 3600
        break_hours = (shift.unpaid_break_minutes or 0) / 60
        if raw_hours > break_hours:
            working_hours = round(raw_hours - break_hours, 2)
        else:
            working_hours = round(raw_hours, 2)

        expected = expected_shift_hours(shift)
        overtime_hours = round(max(working_hours - expected, 0), 2)

        shift_end = datetime.combine(check_in.date(), shift.end_time)
        if check_out < shift_end:
            early_leave_minutes = int((shift_end - check_out).total_seconds() // 60)

        if working_hours < 4:
            status = "Half Day"
        elif late_minutes > 0:
            status = "Late"
        else:
            status = "Present"

    return {
        "late_minutes": late_minutes,
        "early_leave_minutes": early_leave_minutes,
        "working_hours": working_hours,
        "overtime_hours": overtime_hours,
        "status": status,
    }


def apply_metrics(record: Attendance, shift: Shift) -> None:
    metrics = compute_metrics(
        check_in=record.check_in,
        check_out=record.check_out,
        shift=shift,
    )
    record.late_minutes = metrics["late_minutes"]
    record.early_leave_minutes = metrics["early_leave_minutes"]
    record.working_hours = metrics["working_hours"]
    record.overtime_hours = metrics["overtime_hours"]
    record.status = metrics["status"]


def _has_approved_wfh(db: Session, employee_id: int, day: date) -> bool:
    return (
        db.query(WfhRequest)
        .filter(
            WfhRequest.employee_id == employee_id,
            WfhRequest.request_date == day,
            WfhRequest.status == "Approved",
        )
        .first()
        is not None
    )


def check_in(
    db: Session,
    employee: Employee,
    *,
    work_mode: str = "office",
    source: str = "web",
    notes: str | None = None,
) -> Attendance:
    work_mode = (work_mode or "office").lower()
    if work_mode not in WORK_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="work_mode must be 'office' or 'wfh'.",
        )

    now = current_datetime()
    today = now.date()
    policy = get_or_create_policy(db)
    shift = resolve_shift(db, employee)

    existing = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date == today,
        )
        .with_for_update()
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already recorded for today.",
        )

    if work_mode == "wfh":
        allowed = policy.allow_direct_wfh or _has_approved_wfh(db, employee.id, today)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WFH check-in is not allowed without an approved WFH request.",
            )

    record = Attendance(
        employee_id=employee.id,
        attendance_date=today,
        check_in=now,
        check_out=None,
        work_mode=work_mode,
        source=source or "web",
        notes=notes,
        shift_id=shift.id,
    )
    apply_metrics(record, shift)
    db.add(record)
    db.flush()

    write_audit_log(
        db,
        actor_id=employee.id,
        action="attendance.check_in",
        resource_type="attendance",
        resource_id=record.id,
        after=attendance_snapshot(record),
    )
    db.commit()
    db.refresh(record)
    return record


def check_out(db: Session, employee: Employee, notes: str | None = None) -> Attendance:
    now = current_datetime()
    today = now.date()
    shift = resolve_shift(db, employee)

    record = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date == today,
        )
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No open check-in found for today.",
        )
    if record.check_out is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already checked out for today.",
        )

    before = attendance_snapshot(record)
    record.check_out = now
    if notes:
        record.notes = notes
    apply_metrics(record, shift)

    write_audit_log(
        db,
        actor_id=employee.id,
        action="attendance.check_out",
        resource_type="attendance",
        resource_id=record.id,
        before=before,
        after=attendance_snapshot(record),
    )
    db.commit()
    db.refresh(record)
    return record


def create_wfh_request(
    db: Session,
    employee: Employee,
    *,
    request_date: date,
    reason: str,
) -> WfhRequest:
    existing = (
        db.query(WfhRequest)
        .filter(
            WfhRequest.employee_id == employee.id,
            WfhRequest.request_date == request_date,
            WfhRequest.status.in_(["Pending", "Approved"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A WFH request already exists for this date.",
        )

    request = WfhRequest(
        employee_id=employee.id,
        request_date=request_date,
        reason=reason,
        status="Pending",
    )
    db.add(request)
    db.flush()

    notify(
        db,
        employee_id=employee.reporting_manager_id,
        title="WFH request pending",
        body=f"{employee.first_name} {employee.last_name} requested WFH on {request_date}.",
        related_type="wfh_request",
        related_id=request.id,
    )
    write_audit_log(
        db,
        actor_id=employee.id,
        action="wfh.request",
        resource_type="wfh_request",
        resource_id=request.id,
        after={"request_date": str(request_date), "reason": reason},
    )
    db.commit()
    db.refresh(request)
    return request


def review_wfh_request(
    db: Session,
    reviewer: Employee,
    request_id: int,
    *,
    approved: bool,
    comment: str | None = None,
) -> WfhRequest:
    request = db.query(WfhRequest).filter(WfhRequest.id == request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="WFH request not found.")
    if request.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WFH request is already reviewed.",
        )

    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if employee is None or not can_review_employee(reviewer, employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot review this WFH request.",
        )

    request.status = "Approved" if approved else "Rejected"
    request.reviewed_by = reviewer.id
    request.reviewed_at = current_datetime()
    request.review_comment = comment

    notify(
        db,
        employee_id=request.employee_id,
        title=f"WFH request {request.status.lower()}",
        body=f"Your WFH request for {request.request_date} was {request.status.lower()}.",
        related_type="wfh_request",
        related_id=request.id,
    )
    write_audit_log(
        db,
        actor_id=reviewer.id,
        action="wfh.review",
        resource_type="wfh_request",
        resource_id=request.id,
        after={"status": request.status, "comment": comment},
    )
    db.commit()
    db.refresh(request)
    return request


def create_correction(
    db: Session,
    employee: Employee,
    *,
    original_attendance_id: int,
    requested_check_in: datetime | None,
    requested_check_out: datetime | None,
    requested_work_mode: str | None,
    reason: str,
) -> AttendanceCorrection:
    record = (
        db.query(Attendance)
        .filter(
            Attendance.id == original_attendance_id,
            Attendance.employee_id == employee.id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found.",
        )

    pending = (
        db.query(AttendanceCorrection)
        .filter(
            AttendanceCorrection.original_attendance_id == record.id,
            AttendanceCorrection.status == "Pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending correction already exists for this attendance record.",
        )

    if requested_work_mode:
        requested_work_mode = requested_work_mode.lower()
        if requested_work_mode not in WORK_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="requested_work_mode must be 'office' or 'wfh'.",
            )

    correction = AttendanceCorrection(
        employee_id=employee.id,
        original_attendance_id=record.id,
        requested_check_in=requested_check_in,
        requested_check_out=requested_check_out,
        requested_work_mode=requested_work_mode,
        reason=reason,
        status="Pending",
    )
    db.add(correction)
    db.flush()

    notify(
        db,
        employee_id=employee.reporting_manager_id,
        title="Attendance correction pending",
        body=(
            f"{employee.first_name} {employee.last_name} requested an attendance "
            f"correction for {record.attendance_date}."
        ),
        related_type="attendance_correction",
        related_id=correction.id,
    )
    write_audit_log(
        db,
        actor_id=employee.id,
        action="attendance.correction.request",
        resource_type="attendance_correction",
        resource_id=correction.id,
        after={
            "attendance_id": record.id,
            "requested_check_in": str(requested_check_in) if requested_check_in else None,
            "requested_check_out": str(requested_check_out) if requested_check_out else None,
            "requested_work_mode": requested_work_mode,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(correction)
    return correction


def review_correction(
    db: Session,
    reviewer: Employee,
    correction_id: int,
    *,
    approved: bool,
    comment: str | None = None,
) -> AttendanceCorrection:
    correction = (
        db.query(AttendanceCorrection)
        .filter(AttendanceCorrection.id == correction_id)
        .first()
    )
    if correction is None:
        raise HTTPException(status_code=404, detail="Correction request not found.")
    if correction.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Correction is already reviewed.",
        )

    employee = db.query(Employee).filter(Employee.id == correction.employee_id).first()
    if employee is None or not can_review_employee(reviewer, employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot review this correction.",
        )

    record = (
        db.query(Attendance)
        .filter(Attendance.id == correction.original_attendance_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found.")

    before = attendance_snapshot(record)

    if approved:
        if correction.requested_check_in is not None:
            record.check_in = correction.requested_check_in
        if correction.requested_check_out is not None:
            record.check_out = correction.requested_check_out
        if correction.requested_work_mode:
            record.work_mode = correction.requested_work_mode
        apply_metrics(record, resolve_shift(db, employee))

    correction.status = "Approved" if approved else "Rejected"
    correction.reviewed_by = reviewer.id
    correction.reviewed_at = current_datetime()
    correction.review_comment = comment

    notify(
        db,
        employee_id=correction.employee_id,
        title=f"Attendance correction {correction.status.lower()}",
        body=(
            f"Your attendance correction for {record.attendance_date} "
            f"was {correction.status.lower()}."
        ),
        related_type="attendance_correction",
        related_id=correction.id,
    )
    write_audit_log(
        db,
        actor_id=reviewer.id,
        action="attendance.correction.review",
        resource_type="attendance_correction",
        resource_id=correction.id,
        before=before,
        after={
            "status": correction.status,
            "attendance": attendance_snapshot(record),
            "comment": comment,
        },
    )
    db.commit()
    db.refresh(correction)
    return correction


def list_wfh_requests(db: Session, user: Employee, status_filter: str | None = None):
    query = db.query(WfhRequest)
    if not is_org_admin(user):
        if role_name(user) == "Manager":
            team_ids = [
                row[0]
                for row in db.query(Employee.id)
                .filter(Employee.reporting_manager_id == user.id)
                .all()
            ]
            query = query.filter(
                WfhRequest.employee_id.in_([user.id, *team_ids])
            )
        else:
            query = query.filter(WfhRequest.employee_id == user.id)
    if status_filter:
        query = query.filter(WfhRequest.status == status_filter)
    return query.order_by(WfhRequest.created_at.desc()).all()


def list_corrections(db: Session, user: Employee, status_filter: str | None = None):
    query = db.query(AttendanceCorrection)
    if not is_org_admin(user):
        if role_name(user) == "Manager":
            team_ids = [
                row[0]
                for row in db.query(Employee.id)
                .filter(Employee.reporting_manager_id == user.id)
                .all()
            ]
            query = query.filter(
                AttendanceCorrection.employee_id.in_([user.id, *team_ids])
            )
        else:
            query = query.filter(AttendanceCorrection.employee_id == user.id)
    if status_filter:
        query = query.filter(AttendanceCorrection.status == status_filter)
    return query.order_by(AttendanceCorrection.created_at.desc()).all()


def update_policy(db: Session, user: Employee, allow_direct_wfh: bool) -> AttendancePolicy:
    policy = get_or_create_policy(db)
    before = {"allow_direct_wfh": policy.allow_direct_wfh}
    policy.allow_direct_wfh = allow_direct_wfh
    write_audit_log(
        db,
        actor_id=user.id,
        action="attendance.policy.update",
        resource_type="attendance_policy",
        resource_id=policy.id,
        before=before,
        after={"allow_direct_wfh": allow_direct_wfh},
    )
    db.commit()
    db.refresh(policy)
    return policy


def _approved_leave_dates(db: Session, employee_id: int, start: date, end: date) -> set[date]:
    leaves = (
        db.query(Leave)
        .filter(
            Leave.employee_id == employee_id,
            Leave.status == "Approved",
            Leave.start_date <= end,
            Leave.end_date >= start,
        )
        .all()
    )
    covered: set[date] = set()
    for leave in leaves:
        cursor = leave.start_date if isinstance(leave.start_date, date) else leave.start_date.date()
        last = leave.end_date if isinstance(leave.end_date, date) else leave.end_date.date()
        while cursor <= last:
            if start <= cursor <= end:
                covered.add(cursor)
            cursor += timedelta(days=1)
    return covered


def build_attendance_report(
    db: Session,
    user: Employee,
    *,
    start: date,
    end: date,
    department_id: int | None = None,
) -> dict:
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'to' must be on or after 'from'.",
        )

    policy = get_or_create_policy(db)
    weekends = parse_weekend_days(policy)
    holidays = {
        row.holiday_date
        for row in db.query(Holiday)
        .filter(Holiday.holiday_date >= start, Holiday.holiday_date <= end)
        .all()
    }

    working_days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() not in weekends and cursor not in holidays:
            working_days.append(cursor)
        cursor += timedelta(days=1)

    employees_query = db.query(Employee).filter(Employee.is_active.is_(True))
    if department_id is not None:
        employees_query = employees_query.filter(Employee.department_id == department_id)

    if is_org_admin(user):
        employees = employees_query.all()
    elif role_name(user) == "Manager":
        employees = employees_query.filter(
            Employee.reporting_manager_id == user.id
        ).all()
    else:
        employees = employees_query.filter(Employee.id == user.id).all()

    employee_ids = [emp.id for emp in employees]
    records = []
    if employee_ids:
        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id.in_(employee_ids),
                Attendance.attendance_date >= start,
                Attendance.attendance_date <= end,
            )
            .all()
        )

    records_by_emp: dict[int, dict[date, Attendance]] = {}
    for record in records:
        day = record.attendance_date
        if isinstance(day, datetime):
            day = day.date()
        records_by_emp.setdefault(record.employee_id, {})[day] = record

    rows = []
    totals = {
        "present_days": 0,
        "absent_days": 0,
        "late_days": 0,
        "wfh_days": 0,
        "office_days": 0,
        "overtime_hours": 0.0,
        "unpaid_days": 0,
        "working_days": len(working_days),
    }

    for emp in employees:
        by_date = records_by_emp.get(emp.id, {})
        leave_dates = _approved_leave_dates(db, emp.id, start, end)
        present_days = 0
        absent_days = 0
        late_days = 0
        wfh_days = 0
        office_days = 0
        overtime_hours = 0.0
        unpaid_days = 0

        for day in working_days:
            record = by_date.get(day)
            if record is None:
                absent_days += 1
                if day not in leave_dates:
                    unpaid_days += 1
                continue

            present_days += 1
            if record.late_minutes or record.status == "Late":
                late_days += 1
            if record.work_mode == "wfh" or record.status == "Work From Home":
                wfh_days += 1
            else:
                office_days += 1
            overtime_hours += record.overtime_hours or 0

        row = {
            "employee_id": emp.id,
            "employee_code": emp.employee_code,
            "name": f"{emp.first_name} {emp.last_name}",
            "department_id": emp.department_id,
            "present_days": present_days,
            "absent_days": absent_days,
            "late_days": late_days,
            "wfh_days": wfh_days,
            "office_days": office_days,
            "overtime_hours": round(overtime_hours, 2),
            "unpaid_days": unpaid_days,
        }
        rows.append(row)
        for key in (
            "present_days",
            "absent_days",
            "late_days",
            "wfh_days",
            "office_days",
            "unpaid_days",
        ):
            totals[key] += row[key]
        totals["overtime_hours"] = round(totals["overtime_hours"] + overtime_hours, 2)

    return {
        "from": start,
        "to": end,
        "department_id": department_id,
        "working_days": len(working_days),
        "totals": totals,
        "employees": rows,
    }
