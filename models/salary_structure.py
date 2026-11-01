from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class SalaryStructure(Base):
    __tablename__ = "salary_structures"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "effective_from",
            name="uq_salary_structures_employee_effective_from",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    basic_salary: Mapped[float] = mapped_column(Float, nullable=False)
    hra: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    allowance: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    recurring_deduction: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
    )
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    employee = relationship("Employee")
