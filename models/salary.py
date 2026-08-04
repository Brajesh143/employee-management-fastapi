from sqlalchemy import (
    Integer,
    Float,
    String,
    Date,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from database import Base


class Salary(Base):

    __tablename__ = "salary"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id")
    )

    month: Mapped[int] = mapped_column(
        Integer
    )

    year: Mapped[int] = mapped_column(
        Integer
    )

    basic_salary: Mapped[float] = mapped_column(
        Float
    )

    hra: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    allowance: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    bonus: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    deduction: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    tax: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    net_salary: Mapped[float] = mapped_column(
        Float
    )

    payment_status: Mapped[str] = mapped_column(
        String(20),
        default="Pending"
    )

    payment_date: Mapped[datetime | None] = mapped_column(
        Date,
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

    employee = relationship("Employee")