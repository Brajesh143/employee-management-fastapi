from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AttendanceCorrection(Base):
    __tablename__ = "attendance_corrections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    original_attendance_id: Mapped[int] = mapped_column(
        ForeignKey("attendance.id"), nullable=False, index=True
    )
    requested_check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_work_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Pending", nullable=False, index=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    employee = relationship("Employee", foreign_keys=[employee_id])
    reviewer = relationship("Employee", foreign_keys=[reviewed_by])
    attendance = relationship("Attendance")
