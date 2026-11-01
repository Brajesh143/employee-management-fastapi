from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

GoalStatus = Literal["Not started", "In progress", "Completed", "At risk"]
ReviewStatus = Literal["Draft", "Completed"]


class PerformanceReviewCreate(BaseModel):
    employee_id: int = Field(gt=0)
    period_start: date
    period_end: date
    rating: float = Field(ge=1, le=5)
    strengths: str = Field(min_length=3, max_length=5000)
    areas_to_improve: str = Field(min_length=3, max_length=5000)
    comments: str | None = Field(default=None, max_length=5000)
    status: ReviewStatus = "Draft"

    @model_validator(mode="after")
    def validate_period(self) -> "PerformanceReviewCreate":
        if self.period_end < self.period_start:
            raise ValueError("Review period end cannot be before its start.")
        self.strengths = self.strengths.strip()
        self.areas_to_improve = self.areas_to_improve.strip()
        if not self.strengths or not self.areas_to_improve:
            raise ValueError("Strengths and improvement areas are required.")
        return self

    model_config = {"extra": "forbid"}


class PerformanceReviewUpdate(BaseModel):
    rating: float | None = Field(default=None, ge=1, le=5)
    strengths: str | None = Field(default=None, min_length=3, max_length=5000)
    areas_to_improve: str | None = Field(
        default=None,
        min_length=3,
        max_length=5000,
    )
    comments: str | None = Field(default=None, max_length=5000)
    status: ReviewStatus | None = None

    @model_validator(mode="after")
    def require_changes(self) -> "PerformanceReviewUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one review field must be provided.")
        for field in ("strengths", "areas_to_improve", "comments"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip())
                if field != "comments" and not getattr(self, field):
                    raise ValueError(f"{field.replace('_', ' ').title()} is required.")
        return self

    model_config = {"extra": "forbid"}


class PerformanceReviewResponse(BaseModel):
    id: int
    employee_id: int
    reviewer_id: int
    period_start: date
    period_end: date
    rating: float
    strengths: str
    areas_to_improve: str
    comments: str | None
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerformanceGoalCreate(BaseModel):
    employee_id: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=150)
    description: str = Field(min_length=3, max_length=3000)
    metric: str = Field(min_length=2, max_length=100)
    target_value: float = Field(gt=0, le=1_000_000_000)
    current_value: float = Field(default=0, ge=0, le=1_000_000_000)
    unit: str = Field(default="", max_length=30)
    due_date: date

    @model_validator(mode="after")
    def normalize_text(self) -> "PerformanceGoalCreate":
        for field in ("title", "description", "metric", "unit"):
            setattr(self, field, getattr(self, field).strip())
        if not self.title or not self.description or not self.metric:
            raise ValueError("Goal title, description, and KPI metric are required.")
        return self

    model_config = {"extra": "forbid"}


class PerformanceGoalProgress(BaseModel):
    current_value: float = Field(ge=0, le=1_000_000_000)
    status: GoalStatus

    model_config = {"extra": "forbid"}


class PerformanceGoalResponse(BaseModel):
    id: int
    employee_id: int
    created_by: int
    title: str
    description: str
    metric: str
    target_value: float
    current_value: float
    unit: str
    due_date: date
    status: GoalStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
