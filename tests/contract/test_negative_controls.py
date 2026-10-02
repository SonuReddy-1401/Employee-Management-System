import uuid
import pytest
from jsonschema import ValidationError
from tests.contract.schema_helper import validate_schema


def test_negative_employee_missing_status():
    broken_emp = {
        "id": str(uuid.uuid4()),
        "name": "Jane Doe",
        "email": "jane@example.com",
        "department": "Engineering",
        "designation": "Developer"
        # missing status
    }
    with pytest.raises(ValidationError):
        validate_schema(broken_emp, "employee.json")


def test_negative_payslip_string_gross_salary():
    broken_payslip = {
        "id": str(uuid.uuid4()),
        "employee_id": str(uuid.uuid4()),
        "month": "2026-01",
        "gross_salary": "INVALID_STRING_SALARY",  # should be number
        "unpaid_leave_days": 0,
        "deduction": 0.0,
        "net_salary": 2000.0
    }
    with pytest.raises(ValidationError):
        validate_schema(broken_payslip, "payslip.json")


def test_negative_event_envelope_invalid_uuid():
    broken_envelope = {
        "event_id": "not-a-valid-uuid",  # invalid uuid format
        "type": "EmployeeOnboarded",
        "occurred_at": "2026-10-02T12:00:00Z",
        "correlation_id": str(uuid.uuid4()),
        "payload": {}
    }
    with pytest.raises(ValidationError):
        validate_schema(broken_envelope, "event-envelope.json")


def test_negative_event_wrong_payload_type():
    # Pass EmployeeOnboarded payload to LeaveRequested schema
    wrong_payload = {
        "employee_id": str(uuid.uuid4()),
        "name": "John Smith",
        "email": "john@example.com"
        # missing leave_id, start_date, end_date, leave_type, days
    }
    with pytest.raises(ValidationError):
        validate_schema(wrong_payload, "LeaveRequested.json")


def test_negative_error_response_missing_code():
    broken_error = {
        "error": {
            "message": "Something went wrong"
            # missing code
        }
    }
    with pytest.raises(ValidationError):
        validate_schema(broken_error, "error-response.json")
