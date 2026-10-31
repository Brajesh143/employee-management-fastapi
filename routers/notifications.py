from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database import get_db
from models.employee import Employee
from models.notification import Notification
from schemas.attendence import NotificationResponse

router = APIRouter()


@router.get(
    "/",
    response_model=list[NotificationResponse],
)
def list_notifications(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return (
        db.query(Notification)
        .filter(Notification.employee_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.employee_id == current_user.id,
        )
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification
