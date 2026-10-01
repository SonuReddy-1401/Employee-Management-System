from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID
from ems_common.errors import EMSError


def count_weekdays(start_date: date, end_date: date) -> int:
    if end_date < start_date:
        return 0
    cur = start_date
    weekdays = 0
    while cur <= end_date:
        if cur.weekday() < 5:  # Monday to Friday
            weekdays += 1
        cur += timedelta(days=1)
    return weekdays


def validate_leave_range(start_date: date, end_date: date) -> int:
    if end_date < start_date:
        raise EMSError(
            code="VALIDATION_ERROR",
            message="end_date cannot be before start_date",
            status_code=422,
        )
    if start_date.year != end_date.year:
        raise EMSError(
            code="VALIDATION_ERROR",
            message="Leave request cannot cross calendar years",
            status_code=422,
        )
    days = count_weekdays(start_date, end_date)
    if days == 0:
        raise EMSError(
            code="VALIDATION_ERROR",
            message="Leave request must contain at least one weekday",
            status_code=422,
        )
    return days


class LeaveStateMachine:
    ALLOWED_TRANSITIONS = {
        "PENDING": ["APPROVED", "REJECTED", "CANCELLED"],
        "APPROVED": ["CANCELLED"],
    }

    @classmethod
    def validate_transition(cls, current_status: str, target_status: str) -> None:
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise EMSError(
                code="INVALID_STATE_TRANSITION",
                message=f"Cannot transition leave status from {current_status} to {target_status}",
                status_code=409,
            )


def ranges_overlap(start1: date, end1: date, start2: date, end2: date) -> bool:
    return max(start1, start2) <= min(end1, end2)


def calculate_balance(allowance: int, used: int) -> Dict[str, int]:
    return {
        "allowance": allowance,
        "used": used,
        "remaining": allowance - used,
    }


def can_create_leave(jwt_role: str, jwt_sub: str, target_employee_id: str) -> bool:
    if jwt_role in ("HR", "ADMIN"):
        return True
    return jwt_sub == target_employee_id


def can_decide_leave(
    jwt_role: str, jwt_sub: str, leave_employee_id: str, leave_manager_id: Optional[str]
) -> bool:
    if jwt_sub == leave_employee_id:
        return False
    if jwt_role in ("HR", "ADMIN"):
        return True
    if jwt_role == "MANAGER":
        return leave_manager_id is not None and str(leave_manager_id) == jwt_sub
    return False


def can_cancel_leave(jwt_role: str, jwt_sub: str, leave_employee_id: str) -> bool:
    if jwt_role in ("HR", "ADMIN"):
        return True
    return jwt_sub == leave_employee_id


def can_view_balance(jwt_role: str, jwt_sub: str, target_employee_id: str) -> bool:
    if jwt_role in ("HR", "ADMIN"):
        return True
    return jwt_sub == target_employee_id
