from datetime import datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "attendance_date",
            name="uq_attendance_employee_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )

    attendance_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)

    check_in: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    working_hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="Present", nullable=False)
    work_mode: Mapped[str] = mapped_column(String(20), default="office", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="web", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    employee = relationship("Employee")
    shift = relationship("Shift")
