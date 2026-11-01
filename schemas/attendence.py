from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

WorkMode = Literal["office", "wfh"]
AttendanceStatus = Literal[
    "Present",
    "Absent",
    "Half Day",
    "Late",
    "Work From Home",
    "Holiday",
]


class AttendanceBase(BaseModel):
    employee_id: Annotated[int, Field(description="ID of the employee")]
    attendance_date: Annotated[date | datetime, Field(description="Date of attendance")]
    check_in: Annotated[datetime, Field(description="Check-in time")]
    check_out: Annotated[
        datetime | None,
        Field(default=None, description="Check-out time"),
    ]
    working_hours: Annotated[float | None, Field(default=None, description="Working hours")]
    overtime_hours: Annotated[float | None, Field(default=None, description="Overtime hours")]
    status: Annotated[
        AttendanceStatus | None,
        Field(default=None, description="Attendance status"),
    ]


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    check_out: Annotated[datetime | None, Field(default=None)]
    working_hours: Annotated[float | None, Field(default=None)]
    overtime_hours: Annotated[float | None, Field(default=None)]
    status: Annotated[AttendanceStatus | None, Field(default=None)]


class AttendenceByEmployee(BaseModel):
    employee_id: int


class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    attendance_date: date | datetime
    check_in: datetime
    check_out: datetime | None
    working_hours: float
    overtime_hours: float
    late_minutes: int = 0
    early_leave_minutes: int = 0
    status: str
    work_mode: str = "office"
    source: str = "web"
    notes: str | None = None
    shift_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CheckInRequest(BaseModel):
    work_mode: WorkMode = "office"
    source: str = "web"
    notes: str | None = None


class CheckOutRequest(BaseModel):
    notes: str | None = None


class WfhRequestCreate(BaseModel):
    request_date: date
    reason: str = Field(min_length=3)


class WfhRequestResponse(BaseModel):
    id: int
    employee_id: int
    request_date: date
    reason: str
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CorrectionCreate(BaseModel):
    original_attendance_id: int
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    requested_work_mode: WorkMode | None = None
    reason: str = Field(min_length=3)

    @field_validator("requested_check_in", "requested_check_out")
    @classmethod
    def normalize_requested_datetime(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def require_correction_value(self) -> "CorrectionCreate":
        if (
            self.requested_check_in is None
            and self.requested_check_out is None
            and self.requested_work_mode is None
        ):
            raise ValueError("At least one attendance field must be corrected.")
        if (
            self.requested_check_in is not None
            and self.requested_check_out is not None
            and self.requested_check_out < self.requested_check_in
        ):
            raise ValueError("Check-out must be after check-in.")
        return self


class CorrectionResponse(BaseModel):
    id: int
    employee_id: int
    original_attendance_id: int
    requested_check_in: datetime | None
    requested_check_out: datetime | None
    requested_work_mode: str | None
    reason: str
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewRequest(BaseModel):
    comment: str | None = None


class AttendancePolicyResponse(BaseModel):
    id: int
    allow_direct_wfh: bool
    weekend_days: str

    model_config = {"from_attributes": True}


class AttendancePolicyUpdate(BaseModel):
    allow_direct_wfh: bool


class NotificationResponse(BaseModel):
    id: int
    employee_id: int
    title: str
    body: str
    related_type: str | None
    related_id: int | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
