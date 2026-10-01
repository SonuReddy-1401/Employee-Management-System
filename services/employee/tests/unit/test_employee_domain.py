from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from ems_common.errors import EMSError
from services.employee.app.domain.employee import (
    compute_pagination,
    extract_updatable_fields,
    validate_manager_not_self,
)
from services.employee.app.schemas.employee import EmployeeCreateRequest, EmployeeRole


def test_manager_not_self_rule():
    emp_id = uuid4()
    other_id = uuid4()

    # Valid manager
    validate_manager_not_self(emp_id, other_id)
    validate_manager_not_self(emp_id, None)

    # Self manager raises 422 EMSError
    with pytest.raises(EMSError) as exc_info:
        validate_manager_not_self(emp_id, emp_id)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert "cannot be their own manager" in exc_info.value.message


def test_pagination_math():
    assert compute_pagination(1, 20) == (0, 20)
    assert compute_pagination(2, 20) == (20, 20)
    assert compute_pagination(3, 10) == (20, 10)
    # Edge case clamping
    assert compute_pagination(0, 150) == (0, 100)


def test_updatable_fields_extraction():
    data = {
        "name": "Bob",
        "department": "Engineering",
        "status": "ACTIVE",  # Should be ignored
        "id": uuid4(),  # Should be ignored
        "invalid_field": "test",  # Should be ignored
    }
    extracted = extract_updatable_fields(data)
    assert extracted == {"name": "Bob", "department": "Engineering"}


def test_schema_validations():
    # Bad email
    with pytest.raises(ValidationError):
        EmployeeCreateRequest(
            name="Alice",
            email="invalid-email",
            department="HR",
            designation="Manager",
            initial_password="Password123!",
            monthly_salary=Decimal("5000.00"),
        )

    # Short password
    with pytest.raises(ValidationError):
        EmployeeCreateRequest(
            name="Alice",
            email="alice@example.com",
            department="HR",
            designation="Manager",
            initial_password="short",
            monthly_salary=Decimal("5000.00"),
        )

    # Non-positive salary
    with pytest.raises(ValidationError):
        EmployeeCreateRequest(
            name="Alice",
            email="alice@example.com",
            department="HR",
            designation="Manager",
            initial_password="Password123!",
            monthly_salary=Decimal("0.00"),
        )

    with pytest.raises(ValidationError):
        EmployeeCreateRequest(
            name="Alice",
            email="alice@example.com",
            department="HR",
            designation="Manager",
            initial_password="Password123!",
            monthly_salary=Decimal("-100.00"),
        )

    # Invalid role
    with pytest.raises(ValidationError):
        EmployeeCreateRequest(
            name="Alice",
            email="alice@example.com",
            department="HR",
            designation="Manager",
            role="SUPERROLE",  # type: ignore
            initial_password="Password123!",
            monthly_salary=Decimal("5000.00"),
        )
