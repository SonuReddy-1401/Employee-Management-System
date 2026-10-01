from typing import Any, Dict, Tuple
from uuid import UUID
from ems_common.errors import EMSError

UPDATABLE_FIELDS = {"name", "email", "department", "designation", "manager_id"}


def validate_manager_not_self(employee_id: UUID, manager_id: UUID | None) -> None:
    if manager_id is not None and employee_id == manager_id:
        raise EMSError(
            code="VALIDATION_ERROR",
            message="Employee cannot be their own manager",
            status_code=422,
        )


def compute_pagination(page: int = 1, page_size: int = 20) -> Tuple[int, int]:
    valid_page = max(1, page)
    valid_size = max(1, min(100, page_size))
    offset = (valid_page - 1) * valid_size
    return offset, valid_size


def extract_updatable_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if k in UPDATABLE_FIELDS and v is not None}
