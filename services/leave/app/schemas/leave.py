from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeaveCreateRequest(BaseModel):
    employee_id: UUID
    start_date: date
    end_date: date
    leave_type: str = Field(default="PAID")
    reason: Optional[str] = None

    @field_validator("leave_type")
    @classmethod
    def validate_leave_type(cls, v: str) -> str:
        if v not in ("PAID", "UNPAID"):
            raise ValueError("leave_type must be either PAID or UNPAID")
        return v


class LeaveResponse(BaseModel):
    id: UUID
    employee_id: UUID
    manager_id: Optional[UUID] = None
    start_date: date
    end_date: date
    leave_type: str
    reason: Optional[str] = None
    days: int
    status: str
    decided_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaveListResponse(BaseModel):
    items: List[LeaveResponse]
    total: int
    page: int
    page_size: int


class LeaveBalanceResponse(BaseModel):
    employee_id: UUID
    year: int
    allowance: int
    used: int
    remaining: int
