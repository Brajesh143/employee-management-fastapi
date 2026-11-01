from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

LeaveType = Literal["Sick", "Casual", "Earned", "Maternity", "Paternity"]
LeaveStatus = Literal["Pending", "Approved", "Rejected", "Cancelled"]
ApprovalStage = Literal["manager", "hr", "completed", "rejected", "cancelled"]


class LeaveCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=2000)

    model_config = {"extra": "forbid"}

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_date_range(self) -> "LeaveCreate":
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date.")
        return self


class LeaveUpdate(BaseModel):
    leave_type: LeaveType | None = None
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=2000)

    model_config = {"extra": "forbid"}

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_date_range(self) -> "LeaveUpdate":
        for field in ("leave_type", "start_date", "end_date", "reason"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("End date cannot be before start date.")
        return self


class LeaveCancellation(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LeaveResponse(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: int
    reason: str
    status: LeaveStatus
    approval_stage: ApprovalStage
    approval_manager_id: int | None
    manager_approved_by: int | None
    manager_approved_at: datetime | None
    hr_approved_by: int | None
    hr_approved_at: datetime | None
    approved_by: int | None
    approved_at: datetime | None
    rejected_by: int | None
    rejected_at: datetime | None
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeaveBalanceResponse(BaseModel):
    employee_id: int
    leave_balance: float


class LeaveBalanceUpdate(BaseModel):
    leave_balance: float = Field(ge=0, le=365)

    model_config = {"extra": "forbid"}


class LeaveReviewResponse(BaseModel):
    message: str
    leave: LeaveResponse
    remaining_leave_balance: float
