from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Pending",
        index=True,
    )
    reimbursement_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Not eligible",
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reimbursed_by: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )
    reimbursed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    receipt_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_storage_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    receipt_content_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    receipt_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    employee = relationship("Employee", foreign_keys=[employee_id])
