from sqlalchemy import (
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from database import Base


class Leave(Base):

    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id")
    )

    leave_type: Mapped[str] = mapped_column(
        String(30)
    )

    start_date: Mapped[datetime] = mapped_column(
        Date
    )

    end_date: Mapped[datetime] = mapped_column(
        Date
    )

    total_days: Mapped[int] = mapped_column(
        Integer
    )

    reason: Mapped[str] = mapped_column(
        Text
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Pending"
    )

    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
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

    employee = relationship(
        "Employee",
        foreign_keys=[employee_id],
        back_populates="leaves"
    )