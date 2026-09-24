from datetime import datetime
from pydantic import BaseModel, Field
from typing import Annotated, Literal

class AttendanceBase(BaseModel):
    employee_id: Annotated[
        int,
        Field(
            description="ID of the employee"
        )
    ]
    attendance_date: Annotated[
        datetime,
        Field(
            description="Date of attendance"
        )
    ]
    check_in: Annotated[
        datetime,
        Field(
            description="Check-in time"
        )
    ]
    check_out: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Check-out time"
        )
    ]
    working_hours: Annotated[
        float | None,
        Field(
            default=None,
            description="Working hours"
        )
    ]
    overtime_hours: Annotated[
        float | None,
        Field(
            default=None,
            description="Overtime hours"
        )
    ]
    status: Annotated[
        Literal["Present","Absent","Half Day","Late","Work From Home","Holiday"],
        Field(
            description="Attendance status"
        )
    ]

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceUpdate(BaseModel):
    check_out: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Updated check-out time"
        )
    ]
    working_hours: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated working hours"
        )
    ]
    overtime_hours: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated overtime hours"
        )
    ]
    status: Annotated[
        Literal["Present","Absent","Half Day","Late","Work From Home","Holiday"] | None,
        Field(
            default=None,
            description="Updated attendance status"
        )
    ]


class AttendenceByEmployee(BaseModel):
    employee_id: int

class AttendanceResponse(AttendanceBase):
    id: int
    status: Literal["Present","Absent","Half Day","Late","Work From Home","Holiday"]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
    

    