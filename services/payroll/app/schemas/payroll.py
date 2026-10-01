from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ProfileCreateRequest(BaseModel):
    employee_id: UUID
    monthly_salary: Decimal = Field(..., gt=0)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: UUID
    monthly_salary: Decimal


class PayrollRunResponse(BaseModel):
    month: str
    created: int
    skipped: int


class PayslipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    month: str
    gross_salary: Decimal
    unpaid_leave_days: int
    deduction: Decimal
    net_salary: Decimal
    created_at: datetime
