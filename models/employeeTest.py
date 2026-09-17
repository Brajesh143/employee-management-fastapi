from database import Base
from sqlalchemy.orm import Mapped, MappedColumn
from sqlalchemy import String, Float

class EmployeeTest(Base):
    __tablename__ = "employee_test"

    id: Mapped[int] = MappedColumn(primary_key=True, index=True)
    name: Mapped[str] = MappedColumn(String(20), nullable=False)
    email: Mapped[str] = MappedColumn(String(50), unique=True, nullable=False)
    department: Mapped[str] = MappedColumn(String(30), nullable=False)
    salary: Mapped[float] = MappedColumn(Float, nullable=False)