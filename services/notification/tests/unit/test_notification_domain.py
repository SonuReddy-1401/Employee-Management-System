from datetime import datetime, timezone
from uuid import uuid4
import pytest
from ems_common.errors import EMSError
from ems_common.events import EventEnvelope, EventType
from services.notification.app.domain.notification import build_notification


def test_build_notification_employee_onboarded():
    emp_id = uuid4()
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.EMPLOYEE_ONBOARDED,
        correlation_id=uuid4(),
        payload={"employee_id": str(emp_id), "name": "Jane Doe"},
    )
    res_emp_id, message = build_notification(envelope)
    assert res_emp_id == emp_id
    assert message == "Welcome Jane Doe, your account is ready."


def test_build_notification_leave_requested():
    emp_id = uuid4()
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_REQUESTED,
        correlation_id=uuid4(),
        payload={
            "employee_id": str(emp_id),
            "leave_type": "ANNUAL",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "days": 5,
        },
    )
    res_emp_id, message = build_notification(envelope)
    assert res_emp_id == emp_id
    assert message == "Your ANNUAL leave from 2026-06-01 to 2026-06-05 (5 days) was requested."


def test_build_notification_leave_approved():
    emp_id = uuid4()
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "employee_id": str(emp_id),
            "leave_type": "SICK",
            "start_date": "2026-07-10",
            "end_date": "2026-07-12",
            "days": 2,
        },
    )
    res_emp_id, message = build_notification(envelope)
    assert res_emp_id == emp_id
    assert message == "Your SICK leave from 2026-07-10 to 2026-07-12 (2 days) was approved."


def test_build_notification_leave_rejected():
    emp_id = uuid4()
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_REJECTED,
        correlation_id=uuid4(),
        payload={
            "employee_id": str(emp_id),
            "leave_type": "UNPAID",
            "start_date": "2026-08-01",
            "end_date": "2026-08-05",
            "days": 5,
        },
    )
    res_emp_id, message = build_notification(envelope)
    assert res_emp_id == emp_id
    assert message == "Your UNPAID leave from 2026-08-01 to 2026-08-05 (5 days) was rejected."


def test_build_notification_leave_cancelled():
    emp_id = uuid4()
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_CANCELLED,
        correlation_id=uuid4(),
        payload={
            "employee_id": str(emp_id),
            "leave_type": "ANNUAL",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "days": 2,
        },
    )
    res_emp_id, message = build_notification(envelope)
    assert res_emp_id == emp_id
    assert message == "Your ANNUAL leave from 2026-09-01 to 2026-09-03 (2 days) was cancelled."


def test_build_notification_missing_employee_id():
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.EMPLOYEE_ONBOARDED,
        correlation_id=uuid4(),
        payload={"name": "Alice"},
    )
    with pytest.raises(EMSError) as exc_info:
        build_notification(envelope)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"
