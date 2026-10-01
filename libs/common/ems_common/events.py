from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EventType(str, Enum):
    EMPLOYEE_ONBOARDED = "EmployeeOnboarded"
    LEAVE_REQUESTED = "LeaveRequested"
    LEAVE_APPROVED = "LeaveApproved"
    LEAVE_REJECTED = "LeaveRejected"


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    type: EventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UUID
    payload: Dict[str, Any]
