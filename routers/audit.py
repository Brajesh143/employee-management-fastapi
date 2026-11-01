from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from auth.permissions import require_permission
from database import get_db
from schemas.audit_log import AuditLogResponse
from services.audit import list_audit_logs

router = APIRouter()


@router.get(
    "/",
    response_model=list[AuditLogResponse],
    dependencies=[Depends(require_permission("audit:read"))],
)
def get_audit_logs(
    response: Response,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    actor_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    resource_type: str | None = Query(default=None, min_length=1, max_length=50),
    resource_id: int | None = Query(default=None, ge=1),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
):
    if from_date is not None and from_date.tzinfo is not None:
        from_date = from_date.astimezone(timezone.utc).replace(tzinfo=None)
    if to_date is not None and to_date.tzinfo is not None:
        to_date = to_date.astimezone(timezone.utc).replace(tzinfo=None)
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="'from' must be on or before 'to'.",
        )

    exclusive_to = (
        datetime.combine(to_date.date() + timedelta(days=1), time.min)
        if to_date is not None
        else None
    )
    logs, total = list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_date=from_date,
        to_date=exclusive_to,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    return logs
