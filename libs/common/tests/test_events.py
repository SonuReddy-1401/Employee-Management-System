from uuid import uuid4
from ems_common.events import EventEnvelope, EventType


def test_event_type_enum():
    assert EventType.LEAVE_CANCELLED.value == "LeaveCancelled"
    assert EventType.LEAVE_APPROVED.value == "LeaveApproved"
    assert EventType.LEAVE_REJECTED.value == "LeaveRejected"
    assert EventType.LEAVE_REQUESTED.value == "LeaveRequested"
    assert EventType.EMPLOYEE_ONBOARDED.value == "EmployeeOnboarded"


def test_event_envelope():
    corr_id = uuid4()
    envelope = EventEnvelope(
        type=EventType.LEAVE_CANCELLED,
        correlation_id=corr_id,
        payload={"leave_id": str(uuid4()), "days": 5},
    )
    assert envelope.type == EventType.LEAVE_CANCELLED
    assert envelope.correlation_id == corr_id
