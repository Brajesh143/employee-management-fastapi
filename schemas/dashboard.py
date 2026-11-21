from pydantic import BaseModel


class DashboardSummary(BaseModel):
    employees: int | None
    present_today: int | None
    pending_leaves: int | None
    departments: int | None
