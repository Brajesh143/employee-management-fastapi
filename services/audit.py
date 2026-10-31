import json
from typing import Any

from sqlalchemy.orm import Session

from models.audit_log import AuditLog


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
