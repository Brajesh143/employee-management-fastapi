from datetime import date

from pydantic import BaseModel, Field


class EmployeeExitRequest(BaseModel):
    exit_date: date
    exit_reason: str = Field(min_length=1, max_length=2000)
