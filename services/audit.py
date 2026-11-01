import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def employee_audit_snapshot(employee: Any) -> dict[str, Any]:
    return {
        "id": employee.id,
        "employee_code": employee.employee_code,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "email": employee.email,
        "department_id": employee.department_id,
        "designation_id": employee.designation_id,
        "role_id": employee.role_id,
        "reporting_manager_id": employee.reporting_manager_id,
        "is_active": employee.is_active,
        "status": employee.status,
        "exit_date": employee.exit_date,
        "exit_reason": employee.exit_reason,
    }


def write_audit_log(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None,
    before: Any = None,
    after: Any = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_json=None if before is None else json.dumps(before, default=str),
        after_json=None if after is None else json.dumps(after, default=str),
    )
    db.add(log)
    return log


def list_audit_logs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    actor_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    query = db.query(AuditLog)
    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if resource_type:
        query = query.filter(
            AuditLog.resource_type.ilike(f"%{resource_type.strip()}%")
        )
    if resource_id is not None:
        query = query.filter(AuditLog.resource_id == resource_id)
    if from_date is not None:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date is not None:
        query = query.filter(AuditLog.created_at < to_date)

    total = query.count()
    logs = (
        query.order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return logs, total
