from pydantic import BaseModel, Field, field_validator
from typing import Annotated


class RolePermissionCreate(BaseModel):

    role_id: Annotated[
        int,
        Field(
            gt=0,
            description="Role ID"
        )
    ]

    permission_id: Annotated[
        int,
        Field(
            gt=0,
            description="Permission ID"
        )
    ]


class RolePermissionResponse(RolePermissionCreate):

    id: int

    model_config = {
        "from_attributes": True
    }


class RolePermissionUpdate(BaseModel):
    permission_ids: list[int] = Field(
        description="Complete set of permission IDs to assign to this role."
    )

    @field_validator("permission_ids")
    @classmethod
    def validate_permission_ids(cls, permission_ids: list[int]) -> list[int]:
        if any(permission_id <= 0 for permission_id in permission_ids):
            raise ValueError("Permission IDs must be positive.")
        if len(permission_ids) != len(set(permission_ids)):
            raise ValueError("Permission IDs must not contain duplicates.")
        return permission_ids