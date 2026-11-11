from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class LeaveRequestDraft(BaseModel):
    leave_type: Literal["Sick", "Casual", "Earned", "Maternity", "Paternity"]
    start_date: date
    end_date: date
    total_days: int
    reason: str


class ChatResponse(BaseModel):
    response: str
    leave_draft: LeaveRequestDraft | None = None