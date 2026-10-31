from sqlalchemy.orm import Session

from models.notification import Notification


def notify(
    db: Session,
    *,
    employee_id: int | None,
    title: str,
    body: str,
    related_type: str | None = None,
    related_id: int | None = None,
) -> Notification | None:
    if employee_id is None:
        return None

    notification = Notification(
        employee_id=employee_id,
        title=title,
        body=body,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(notification)
    return notification
