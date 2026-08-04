from pydantic import BaseModel, Field
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