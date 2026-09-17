from pydantic import BaseModel, Field, EmailStr
from typing import Annotated

class EmployeeTestBase(BaseModel):
    name: Annotated[
        str,
        Field(
            min_length=3,
            max_length=20,
            description="Employee name should be String"
        )
    ]

    email: Annotated[
        EmailStr,
        Field(
            max_length=50,
            description="Employee email address"
        )
    ]

    department: Annotated[
        str,
        Field(
            max_length=30,
            description="Employee Department"
        )
    ]

    salary: Annotated[
        float,
        Field(
            description="Employee Salary"
        )
    ]

class EmployeeTestCreate(EmployeeTestBase):
    pass

class EmployeeTestUpdate(BaseModel):
    name: Annotated[
        str | None,
        Field(
            default=None,
            min_length=3,
            max_length=20,
            description="Employee name should be String"
        )
    ]
    
    email: Annotated[
        EmailStr | None,
        Field(
            default=None,
            max_length=50,
            description="Employee email address"
        )
    ]
    
    department: Annotated[
        str | None,
        Field(
            default=None,
            max_length=30,
            description="Employee Department"
        )
    ]
    
    salary: Annotated[
        float | None,
        Field(
            default=None,
            description="Employee Salary"
        )
    ]

class EmployeeTestResponse(EmployeeTestBase):
    pass

    model_config = {
        "from_attributes": True
    }

