from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class SalaryStructureCreate(BaseModel):
    employee_id: int = Field(gt=0)
    basic_salary: float = Field(ge=0, le=100_000_000)
    hra: float = Field(default=0, ge=0, le=100_000_000)
    allowance: float = Field(default=0, ge=0, le=100_000_000)
    recurring_deduction: float = Field(default=0, ge=0, le=100_000_000)
    tax_rate: float = Field(default=0, ge=0, le=100)
    effective_from: date

    model_config = {"extra": "forbid"}


class SalaryStructureResponse(BaseModel):
    id: int
    employee_id: int
    basic_salary: float
    hra: float
    allowance: float
    recurring_deduction: float
    tax_rate: float
    effective_from: date
    created_at: datetime

    model_config = {"from_attributes": True}


class SalaryCreate(BaseModel):
    employee_id: int = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2200)
    basic_salary: float = Field(ge=0)
    hra: float = Field(default=0, ge=0)
    allowance: float = Field(default=0, ge=0)
    bonus: float = Field(default=0, ge=0)
    deduction: float = Field(default=0, ge=0)
    tax: float = Field(default=0, ge=0)
    payment_status: str = "Pending"
    payment_date: date | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_paid_date(self) -> "SalaryCreate":
        if self.payment_status not in {"Pending", "Paid"}:
            raise ValueError("Payment status must be Pending or Paid.")
        if self.payment_status == "Paid" and self.payment_date is None:
            raise ValueError("Payment date is required for a paid salary.")
        return self


class SalaryUpdate(BaseModel):
    payment_status: str
    payment_date: date

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_payment(self) -> "SalaryUpdate":
        if self.payment_status != "Paid":
            raise ValueError("Salary payment can only be marked as Paid.")
        return self


class SalaryResponse(BaseModel):
    id: int
    employee_id: int
    month: int
    year: int
    basic_salary: float
    hra: float
    allowance: float
    bonus: float
    deduction: float
    tax: float
    net_salary: float
    payment_status: str
    payment_date: date | None

    model_config = {"from_attributes": True}


class PayslipResponse(SalaryResponse):
    employee_name: str
    employee_code: str
    email: str


class PayrollRunResponse(BaseModel):
    month: int
    year: int
    generated_count: int
    skipped_count: int
    total_net_pay: float
    salaries: list[SalaryResponse]
