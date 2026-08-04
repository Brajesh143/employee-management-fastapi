# Write sqlalchemy model for department with id, name, description, created_at, updated_at fields. Use declarative base and add __tablename__ attribute. Add relationship with employee model.

from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from database import Base


class Department(Base):
    __tablename__ = "departments"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Department Name
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    # Department Description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Active / Inactive
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationship with Employee
    employees = relationship(
        "Employee",
        back_populates="department",
        cascade="all, delete"
    )

    def __repr__(self):
        return f"<Department(id={self.id}, name='{self.name}')>"