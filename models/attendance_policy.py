from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AttendancePolicy(Base):
    __tablename__ = "attendance_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    allow_direct_wfh: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weekend_days: Mapped[str] = mapped_column(String(20), default="5,6", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # weekend_days uses Python weekday(): 5=Saturday, 6=Sunday
    default_shift_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
