from datetime import date
from uuid import uuid4
import pytest
from ems_common.errors import EMSError
from services.leave.app.domain.leave import (
    LeaveStateMachine,
    calculate_balance,
    can_cancel_leave,
    can_create_leave,
    can_decide_leave,
    can_view_balance,
    count_weekdays,
    ranges_overlap,
    validate_leave_range,
)


def test_count_weekdays():
    # Mon 2026-06-01 to Fri 2026-06-05 = 5 weekdays
    assert count_weekdays(date(2026, 6, 1), date(2026, 6, 5)) == 5
    # Mon 2026-06-01 to Mon 2026-06-08 = 6 weekdays
    assert count_weekdays(date(2026, 6, 1), date(2026, 6, 8)) == 6
    # Sat 2026-06-06 to Sun 2026-06-07 = 0 weekdays
    assert count_weekdays(date(2026, 6, 6), date(2026, 6, 7)) == 0
    # Mon 2026-06-01 to Mon 2026-06-01 = 1 weekday
    assert count_weekdays(date(2026, 6, 1), date(2026, 6, 1)) == 1
    # Sat 2026-06-06 to Sat 2026-06-06 = 0 weekdays
    assert count_weekdays(date(2026, 6, 6), date(2026, 6, 6)) == 0


def test_validate_leave_range():
    # End before start -> 422
    with pytest.raises(EMSError) as exc1:
        validate_leave_range(date(2026, 6, 5), date(2026, 6, 1))
    assert exc1.value.status_code == 422
    assert exc1.value.code == "VALIDATION_ERROR"

    # Crosses year -> 422
    with pytest.raises(EMSError) as exc2:
        validate_leave_range(date(2026, 12, 30), date(2027, 1, 4))
    assert exc2.value.status_code == 422
    assert exc2.value.code == "VALIDATION_ERROR"

    # Weekend-only -> 422
    with pytest.raises(EMSError) as exc3:
        validate_leave_range(date(2026, 6, 6), date(2026, 6, 7))
    assert exc3.value.status_code == 422
    assert exc3.value.code == "VALIDATION_ERROR"

    # Valid -> returns count
    assert validate_leave_range(date(2026, 6, 1), date(2026, 6, 5)) == 5


def test_leave_state_machine_valid_and_invalid():
    # Valid transitions
    LeaveStateMachine.validate_transition("PENDING", "APPROVED")
    LeaveStateMachine.validate_transition("PENDING", "REJECTED")
    LeaveStateMachine.validate_transition("PENDING", "CANCELLED")
    LeaveStateMachine.validate_transition("APPROVED", "CANCELLED")

    # Invalid transitions -> 409
    invalid_pairs = [
        ("REJECTED", "APPROVED"),
        ("CANCELLED", "APPROVED"),
        ("APPROVED", "REJECTED"),
        ("REJECTED", "CANCELLED"),
        ("CANCELLED", "PENDING"),
        ("APPROVED", "PENDING"),
    ]
    for current, target in invalid_pairs:
        with pytest.raises(EMSError) as exc:
            LeaveStateMachine.validate_transition(current, target)
        assert exc.value.status_code == 409
        assert exc.value.code == "INVALID_STATE_TRANSITION"


def test_ranges_overlap():
    # Overlapping
    assert ranges_overlap(
        date(2026, 6, 1), date(2026, 6, 5), date(2026, 6, 4), date(2026, 6, 10)
    )
    # Touching boundary
    assert ranges_overlap(
        date(2026, 6, 1), date(2026, 6, 5), date(2026, 6, 5), date(2026, 6, 10)
    )
    # Non-overlapping
    assert not ranges_overlap(
        date(2026, 6, 1), date(2026, 6, 5), date(2026, 6, 6), date(2026, 6, 10)
    )


def test_calculate_balance():
    bal = calculate_balance(allowance=20, used=5)
    assert bal == {"allowance": 20, "used": 5, "remaining": 15}


def test_permission_helpers():
    emp_id = str(uuid4())
    other_id = str(uuid4())
    mgr_id = str(uuid4())

    # can_create_leave
    assert can_create_leave("HR", mgr_id, emp_id) is True
    assert can_create_leave("ADMIN", mgr_id, emp_id) is True
    assert can_create_leave("EMPLOYEE", emp_id, emp_id) is True
    assert can_create_leave("EMPLOYEE", emp_id, other_id) is False

    # can_decide_leave
    assert can_decide_leave("HR", mgr_id, emp_id, mgr_id) is True
    assert can_decide_leave("ADMIN", mgr_id, emp_id, mgr_id) is True
    assert can_decide_leave("MANAGER", mgr_id, emp_id, mgr_id) is True
    assert can_decide_leave("MANAGER", other_id, emp_id, mgr_id) is False
    # Self approve forbidden
    assert can_decide_leave("HR", emp_id, emp_id, mgr_id) is False
    assert can_decide_leave("MANAGER", emp_id, emp_id, emp_id) is False
    assert can_decide_leave("EMPLOYEE", other_id, emp_id, mgr_id) is False

    # can_cancel_leave
    assert can_cancel_leave("EMPLOYEE", emp_id, emp_id) is True
    assert can_cancel_leave("EMPLOYEE", other_id, emp_id) is False
    assert can_cancel_leave("HR", other_id, emp_id) is True

    # can_view_balance
    assert can_view_balance("EMPLOYEE", emp_id, emp_id) is True
    assert can_view_balance("EMPLOYEE", emp_id, other_id) is False
    assert can_view_balance("HR", emp_id, other_id) is True
