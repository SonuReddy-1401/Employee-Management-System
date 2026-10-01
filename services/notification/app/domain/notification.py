from typing import Tuple
from uuid import UUID
from ems_common.errors import EMSError
from ems_common.events import EventEnvelope, EventType


def build_notification(envelope: EventEnvelope) -> Tuple[UUID, str]:
    payload = envelope.payload
    emp_id_str = payload.get("employee_id")
    if not emp_id_str:
        raise EMSError(code="VALIDATION_ERROR", message="Event payload missing employee_id", status_code=422)

    emp_id = UUID(str(emp_id_str))

    if envelope.type == EventType.EMPLOYEE_ONBOARDED:
        name = payload.get("name") or payload.get("first_name", "employee")
        message = f"Welcome {name}, your account is ready."
    elif envelope.type in (
        EventType.LEAVE_REQUESTED,
        EventType.LEAVE_APPROVED,
        EventType.LEAVE_REJECTED,
        EventType.LEAVE_CANCELLED,
    ):
        leave_type = payload.get("leave_type", "")
        start_date = payload.get("start_date", "")
        end_date = payload.get("end_date", "")
        days = payload.get("days", "")

        status_map = {
            EventType.LEAVE_REQUESTED: "requested",
            EventType.LEAVE_APPROVED: "approved",
            EventType.LEAVE_REJECTED: "rejected",
            EventType.LEAVE_CANCELLED: "cancelled",
        }
        action = status_map[envelope.type]
        message = f"Your {leave_type} leave from {start_date} to {end_date} ({days} days) was {action}."
    else:
        raise EMSError(code="UNKNOWN_EVENT_TYPE", message=f"Unsupported event type: {envelope.type}", status_code=422)

    return emp_id, message
