from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field

class DepartmentBase(BaseModel):
    name: Annotated[
        str,
        Field(
            min_length=3,
            max_length=50,
            description="Department name",
            examples=["Information Technology"]
        )
    ]

    description: Annotated[
        str | None,
        Field(
            default=None,
            max_length=200,
            description="Department description"
        )
    ]

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Annotated[
        str | None,
        Field(default=None, min_length=3, max_length=50)
    ]

    description: Annotated[
        str | None,
        Field(default=None, max_length=200)
    ]

class DepartmentResponse(DepartmentBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }