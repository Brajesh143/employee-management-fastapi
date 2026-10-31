from datetime import datetime

from pydantic import BaseModel


class EmployeeDocumentResponse(BaseModel):
    id: int
    employee_id: int
    file_name: str
    content_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}
