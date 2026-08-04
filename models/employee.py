from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)

    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary: Mapped[float | None] = mapped_column(Float, nullable=True)
    profile_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    department = relationship("Department", back_populates="employees")
    role = relationship("Role", back_populates="employees")
    leaves = relationship(
        "Leave",
        back_populates="employee",
        foreign_keys="Leave.employee_id"
    )

    @validates("email")
    def validate_email(self, key, value):
        if value is None:
            return value
        return value.strip().lower()

    def __repr__(self) -> str:
        return f"<Employee(id={self.id}, employee_code='{self.employee_code}', email='{self.email}', first_name='{self.first_name}', last_name='{self.last_name}')>"
