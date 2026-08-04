from datetime import date, datetime
from typing import Annotated
from pydantic import BaseModel, Field

class EmployeeBase(BaseModel):
    employee_code: Annotated[
        str,
        Field(
            min_length=3,
            max_length=20,
            description="Unique employee code",
            examples=["EMP001"]
        )
    ]

    first_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=50,
            description="Employee's first name"
        )
    ]

    last_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=50,
            description="Employee's last name"
        )
    ]

    email: Annotated[
        str,
        Field(
            min_length=5,
            max_length=100,
            description="Employee's email address"
        )
    ]

    phone: Annotated[
        str | None,
        Field(
            default=None,
            max_length=15,
            description="Employee's phone number"
        )
    ]

    gender: Annotated[
        str | None,
        Field(
            default=None,
            max_length=10,
            description="Employee's gender"
        )
    ]

    dob: Annotated[
        date | None,
        Field(
            default=None,
            description="Employee's date of birth"
        )
    ]

    joining_date: Annotated[
        date | None,
        Field(
            default=None,
            description="Employee's joining date"
        )
    ]

    department_id: Annotated[
        int | None,
        Field(
            default=None,
            description="ID of the department the employee belongs to"
        )
    ]

    role_id: Annotated[
        int | None,
        Field(
            default=None,
            description="ID of the role assigned to the employee"
        )
    ]

    address: Annotated[
        str | None,
        Field(
            default=None,
            max_length=200,
            description="Employee's address"
        )
    ]

    salary: Annotated[
        float | None,
        Field(
            default=None,
            description="Employee's salary"
        )
    ]

    is_verified: Annotated[
        bool | None,
        Field(
            default=None,
            description="Indicates if the employee's email is verified"
        )
    ]

    profile_image: Annotated[
        str | None,
        Field(
            default=None,
            description="URL of the employee's profile image"
        )
    ]

    status: Annotated[
        str | None,
        Field(
            default=None,
            max_length=20,
            description="Employee's status (e.g., Active, Inactive)"
        )
    ]

class EmployeeCreate(EmployeeBase):
    password: Annotated[
        str,
        Field(
            min_length=8,
            max_length=100,
            description="Employee password"
        )
    ]

class EmployeeUpdate(BaseModel):
    employee_code: Annotated[
        str | None,
        Field(default=None, min_length=3, max_length=20)
    ]

    first_name: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=50)
    ]

    last_name: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=50)
    ]

    email: Annotated[
        str | None,
        Field(default=None, min_length=5, max_length=100)
    ]

    phone: Annotated[
        str | None,
        Field(default=None, max_length=15)
    ]

    gender: Annotated[
        str | None,
        Field(default=None, max_length=10)
    ]

    dob: Annotated[
        date | None,
        Field(default=None)
    ]

    joining_date: Annotated[
        date | None,
        Field(default=None)
    ]

    department_id: Annotated[
        int | None,
        Field(default=None)
    ]

    role_id: Annotated[
        int | None,
        Field(default=None)
    ]

    address: Annotated[
        str | None,
        Field(default=None, max_length=200)
    ]

    salary: Annotated[
        float | None,
        Field(default=None)
    ]

    profile_image: Annotated[
        str | None,
        Field(default=None)
    ]

    status: Annotated[
        str | None,
        Field(default=None, max_length=20)
    ]

class EmployeeResponse(EmployeeBase):
    id: int
    is_active: bool
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }