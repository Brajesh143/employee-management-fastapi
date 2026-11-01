from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ExpenseStatus = Literal["Pending", "Approved", "Rejected"]
ReimbursementStatus = Literal["Not eligible", "Pending", "Paid"]


class ExpenseClaimCreate(BaseModel):
    expense_date: date
    category: str = Field(min_length=2, max_length=50)
    amount: float = Field(gt=0, le=1_000_000)
    description: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def normalize_text(self) -> "ExpenseClaimCreate":
        self.category = self.category.strip()
        self.description = self.description.strip()
        if not self.category or not self.description:
            raise ValueError("Category and description are required.")
        return self

    model_config = {"extra": "forbid"}


class ExpenseReview(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ExpenseClaimResponse(BaseModel):
    id: int
    employee_id: int
    expense_date: date
    category: str
    amount: float
    description: str
    status: ExpenseStatus
    reimbursement_status: ReimbursementStatus
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    reimbursed_by: int | None
    reimbursed_at: datetime | None
    receipt_name: str | None
    receipt_content_type: str | None
    receipt_size: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
