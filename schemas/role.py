from pydantic import BaseModel, Field
from typing import Annotated
from datetime import datetime

class RoleBase(BaseModel):
    name: Annotated[
        str,
        Field(min_length=3, 
              max_length=50, 
              description="Role name", 
              examples=["Admin"])
    ]

    description: Annotated[
        str | None,
        Field(default=None,
              max_length=200, 
              description="Role description")
    ]

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Annotated[
        str | None,
        Field(default=None,
              min_length=3,
              max_length=50)
    ]

    description: Annotated[
        str | None,
        Field(default=None,
              max_length=200)
    ]

class RoleResponse(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
