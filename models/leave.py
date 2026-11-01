from sqlalchemy import (
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from database import Base


class Leave(Base):

    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"),
        index=True,
    )

    leave_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    total_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Pending",
        nullable=False,
        index=True,
    )

    approval_stage: Mapped[str] = mapped_column(
        String(20),
        default="hr",
        nullable=False,
    )

    manager_approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )

    manager_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    hr_approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )

    hr_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    rejected_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )

    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelled_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    @property
    def approval_manager_id(self) -> int | None:
        return self.employee.reporting_manager_id