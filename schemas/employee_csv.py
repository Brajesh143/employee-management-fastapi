from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeImportRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    employee_code: str = Field(min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    phone: str | None = Field(default=None, max_length=15)
    gender: str | None = Field(default=None, max_length=10)
    dob: date | None = None
    joining_date: date | None = None
    department_id: Annotated[int | None, Field(default=None, ge=1)]
    designation_id: Annotated[int | None, Field(default=None, ge=1)]
    role_id: Annotated[int | None, Field(default=None, ge=1)]
    reporting_manager_id: Annotated[int | None, Field(default=None, ge=1)]
    shift_id: Annotated[int | None, Field(default=None, ge=1)]
    address: str | None = Field(default=None, max_length=200)
    salary: Annotated[float | None, Field(default=None, ge=0)]
    status: str | None = Field(default=None, max_length=20)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if (
            not separator
            or not local
            or any(character.isspace() for character in normalized)
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError("Invalid email address")
        return normalized


class EmployeeImportRowResult(BaseModel):
    row: int
    employee_code: str | None
    email: str | None
    valid: bool
    errors: list[str]


class EmployeeImportPreview(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: list[EmployeeImportRowResult]
