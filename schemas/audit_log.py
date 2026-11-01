from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None
    action: str
    resource_type: str
    resource_id: int | None
    before_json: str | None
    after_json: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
