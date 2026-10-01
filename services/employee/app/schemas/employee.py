from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmployeeStatus(str, Enum):
    PENDING_ONBOARDING = "PENDING_ONBOARDING"
    ACTIVE = "ACTIVE"
    ONBOARDING_FAILED = "ONBOARDING_FAILED"


class EmployeeRole(str, Enum):
    ADMIN = "ADMIN"
    HR = "HR"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class EmployeeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    department: str = Field(..., min_length=1)
    designation: str = Field(..., min_length=1)
    manager_id: Optional[UUID] = None
    role: EmployeeRole = EmployeeRole.EMPLOYEE
    initial_password: str = Field(..., min_length=8)
    monthly_salary: Decimal = Field(..., gt=0)


class EmployeeUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, min_length=1)
    designation: Optional[str] = Field(None, min_length=1)
    manager_id: Optional[UUID] = None


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    department: str
    designation: str
    manager_id: Optional[UUID] = None
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    items: List[EmployeeResponse]
    total: int
    page: int
    page_size: int
