from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class PermissionBase(BaseModel):

    name: Annotated[
        str,
        Field(
            min_length=3,
            max_length=100,
            description="Permission name"
        )
    ]

    description: Annotated[
        str | None,
        Field(
            default=None,
            max_length=255,
            description="Permission description"
        )
    ]


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):

    name: Annotated[
        str | None,
        Field(
            default=None,
            min_length=3,
            max_length=100
        )
    ]

    description: Annotated[
        str | None,
        Field(
            default=None,
            max_length=255
        )
    ]


class PermissionResponse(PermissionBase):

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }