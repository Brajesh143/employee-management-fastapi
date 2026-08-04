from datetime import datetime
from pydantic import BaseModel, Field
from typing import Annotated, Literal

class LeaveBase(BaseModel):
    employee_id: Annotated[
        int,
        Field(
            description="ID of the employee"
        )
    ]
    leave_type: Annotated[
        Literal["Sick", "Casual", "Earned", "Maternity", "Paternity"],
        Field(
            description="Type of leave"
        )
    ]
    start_date: Annotated[
        datetime,
        Field(
            description="Start date of leave"
        )
    ]
    end_date: Annotated[
        datetime,
        Field(
            description="End date of leave"
        )
    ]
    total_days: Annotated[
        float,
        Field(
            description="Total days of leave"
        )
    ]
    reason: Annotated[
        str | None,
        Field(
            default=None,
            description="Reason for leave"
        )
    ]
    status: Annotated[
        Literal["Pending", "Approved", "Rejected"],
        Field(
            default="Pending",
            description="Leave status"
        )
    ]
    approved_by: Annotated[
        int | None,
        Field(
            default=None,
            description="ID of the approver"
        )
    ]
    approved_at: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Approval timestamp"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            description="Creation timestamp"
        )
    ]
    updated_at: Annotated[
        datetime,
        Field(
            description="Update timestamp"
        )
    ]

class LeaveCreate(LeaveBase):
    pass

class LeaveUpdate(BaseModel):
    start_date: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Updated start date of leave"
        )
    ]
    end_date: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Updated end date of leave"
        )
    ]
    total_days: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated total days of leave"
        )
    ]
    status: Annotated[
        Literal["Pending", "Approved", "Rejected"] | None,
        Field(
            default=None,
            description="Updated leave status"
        )
    ]

class LeaveResponse(LeaveBase):
    id: int
    status: Literal["Pending", "Approved", "Rejected"]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


