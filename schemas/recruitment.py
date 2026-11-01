from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

OpeningStatus = Literal["Open", "On hold", "Closed"]
CandidateStage = Literal[
    "Applied",
    "Screening",
    "Interview",
    "Offer",
    "Hired",
    "Rejected",
    "Withdrawn",
]
InterviewStatus = Literal["Scheduled", "Completed", "Cancelled"]


class JobOpeningCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    department: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=150)
    employment_type: str = Field(min_length=2, max_length=50)
    description: str = Field(min_length=5, max_length=10_000)
    opened_on: date
    closes_on: date | None = None

    @model_validator(mode="after")
    def normalize_and_validate_dates(self) -> "JobOpeningCreate":
        for field in (
            "title",
            "department",
            "location",
            "employment_type",
            "description",
        ):
            setattr(self, field, getattr(self, field).strip())
            if not getattr(self, field):
                raise ValueError(f"{field.replace('_', ' ').title()} is required.")
        if self.closes_on is not None and self.closes_on < self.opened_on:
            raise ValueError("Closing date cannot be before opening date.")
        return self

    model_config = {"extra": "forbid"}


class JobOpeningUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    department: str | None = Field(default=None, min_length=2, max_length=100)
    location: str | None = Field(default=None, min_length=2, max_length=150)
    employment_type: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, min_length=5, max_length=10_000)
    status: OpeningStatus | None = None
    opened_on: date | None = None
    closes_on: date | None = None

    @model_validator(mode="after")
    def require_changes(self) -> "JobOpeningUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one job opening field must be provided.")
        for field in (
            "title",
            "department",
            "location",
            "employment_type",
            "description",
        ):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip())
        return self

    model_config = {"extra": "forbid"}


class JobOpeningResponse(BaseModel):
    id: int
    title: str
    department: str
    location: str
    employment_type: str
    description: str
    status: OpeningStatus
    opened_on: date
    closes_on: date | None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateCreate(BaseModel):
    job_opening_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    resume_url: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or any(character.isspace() for character in normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Candidate name is required.")
        return value

    model_config = {"extra": "forbid"}


class CandidateUpdate(BaseModel):
    stage: CandidateStage | None = None
    notes: str | None = Field(default=None, max_length=5000)
    resume_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_changes(self) -> "CandidateUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one candidate field must be provided.")
        return self

    model_config = {"extra": "forbid"}


class CandidateResponse(BaseModel):
    id: int
    job_opening_id: int
    full_name: str
    email: str
    phone: str | None
    resume_url: str | None
    source: str | None
    stage: CandidateStage
    notes: str | None
    applied_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewCreate(BaseModel):
    candidate_id: int = Field(gt=0)
    interviewer_id: int = Field(gt=0)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    interview_type: str = Field(min_length=2, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("scheduled_at")
    @classmethod
    def normalize_scheduled_at(cls, value: datetime) -> datetime:
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @field_validator("interview_type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Interview type is required.")
        return value

    model_config = {"extra": "forbid"}


class InterviewUpdate(BaseModel):
    interviewer_id: int | None = Field(default=None, gt=0)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    interview_type: str | None = Field(default=None, min_length=2, max_length=50)
    status: InterviewStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("scheduled_at")
    @classmethod
    def normalize_scheduled_at(cls, value: datetime | None) -> datetime | None:
        if (
            value is not None
            and value.tzinfo is not None
            and value.utcoffset() is not None
        ):
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def require_changes(self) -> "InterviewUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one interview field must be provided.")
        if self.interview_type is not None:
            self.interview_type = self.interview_type.strip()
        return self

    model_config = {"extra": "forbid"}


class InterviewResponse(BaseModel):
    id: int
    candidate_id: int
    interviewer_id: int
    scheduled_at: datetime
    duration_minutes: int
    interview_type: str
    status: InterviewStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
