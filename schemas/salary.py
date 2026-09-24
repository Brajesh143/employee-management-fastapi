from datetime import datetime
from pydantic import BaseModel, Field
from typing import Annotated, Literal

class SalaryBase(BaseModel):
    employee_id: Annotated[
        int,
        Field(
            description="ID of the employee"
        )
    ]
    month: Annotated[
        int,
        Field(
            description="Month of the salary"
        )
    ]
    year: Annotated[
        int,
        Field(
            description="Year of the salary"
        )
    ]
    basic_salary: Annotated[
        float,
        Field(
            description="Basic salary amount"
        )
    ]
    hra: Annotated[
        float | None,
        Field(
            default=None,
            description="House Rent Allowance amount"
        )
    ]
    allowance: Annotated[
        float | None,
        Field(
            default=None,
            description="Allowance amount"
        )
    ]
    bonus: Annotated[
        float | None,
        Field(
            default=None,
            description="Bonus amount"
        )
    ]
    deduction: Annotated[
        float | None,
        Field(
            default=None,
            description="Deduction amount"
        )
    ]
    tax: Annotated[
        float | None,
        Field(
            default=None,
            description="Tax amount"
        )
    ]
    net_salary: Annotated[
        float | None,
        Field(
            default=None,
            description="Net salary amount"
        )
    ]
    payment_status: Annotated[
        Literal["Pending", "Paid"],
        Field(
            default="Pending",
            description="Payment status"
        )
    ]
    payment_date: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Payment date"
        )
    ]

class SalaryCreate(SalaryBase):
    pass

class SalaryUpdate(BaseModel):
    basic_salary: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated basic salary amount"
        )
    ]
    hra: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated House Rent Allowance amount"
        )
    ]
    allowances: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated Allowances amount"
        )
    ]
    bonus: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated Bonus amount"
        )
    ]
    deductions: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated Deductions amount"
        )
    ]
    tax: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated Tax amount"
        )
    ]
    net_salary: Annotated[
        float | None,
        Field(
            default=None,
            description="Updated Net salary amount"
        )
    ]
    payment_status: Annotated[
        Literal["Pending", "Paid"] | None,
        Field(
            default=None,
            description="Updated Payment status"
        )
    ]
    payment_date: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Updated Payment date"
        )
    ]

class SalaryResponse(SalaryBase):
    id: int

    model_config = {
        "from_attributes": True
    }


    