from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class PermissionBase(BaseModel):

    name: Annotated[
        str,
        Field(
            min_length=3,
            max_length=100,
            description="Permission name"
        )
    ]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str) -> str:
        normalized = name.strip().lower()
        if not normalized or any(not part for part in normalized.split(":")):
            raise ValueError("Permission names must use non-empty colon-separated parts.")
        if not all(
            part.replace("_", "").isalnum() and part[0].isalpha()
            for part in normalized.split(":")
        ):
            raise ValueError(
                "Permission names may contain lowercase letters, digits, "
                "underscores, and colons."
            )
        return normalized

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

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: str | None) -> str | None:
        if name is None:
            return None
        normalized = name.strip().lower()
        if not normalized or any(not part for part in normalized.split(":")):
            raise ValueError("Permission names must use non-empty colon-separated parts.")
        if not all(
            part.replace("_", "").isalnum() and part[0].isalpha()
            for part in normalized.split(":")
        ):
            raise ValueError(
                "Permission names may contain lowercase letters, digits, "
                "underscores, and colons."
            )
        return normalized

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