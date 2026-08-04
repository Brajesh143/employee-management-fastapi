from sqlalchemy import (
    Integer,
    Float,
    String,
    Date,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from database import Base


class Attendance(Base):

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id")
    )

    attendance_date: Mapped[datetime] = mapped_column(
        Date
    )

    check_in: Mapped[datetime] = mapped_column(
        DateTime
    )

    check_out: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    working_hours: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    overtime_hours: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="Present"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    employee = relationship("Employee")