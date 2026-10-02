from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ems_common.correlation import get_correlation_id
from ems_common.errors import EMSError
from ems_common.outbox import add_outbox_event
from ems_common.security import get_current_user

from services.leave.app.clients.employee_client import EmployeeClient
from services.leave.app.config import settings
from services.leave.app.domain.leave import (
    LeaveStateMachine,
    calculate_balance,
    can_cancel_leave,
    can_create_leave,
    can_decide_leave,
    can_view_balance,
    validate_leave_range,
)
from services.leave.app.models.leave import Leave
from services.leave.app.repositories.leave_repository import LeaveRepository
from services.leave.app.schemas.leave import (
    LeaveBalanceResponse,
    LeaveCreateRequest,
    LeaveListResponse,
    LeaveResponse,
)

router = APIRouter(tags=["leaves"])


async def get_db(request: Request):
    async with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise



@router.post("/leaves", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def create_leave(
    payload: LeaveCreateRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    user_role = current_user["role"]
    user_sub = current_user["user_id"]

    if not can_create_leave(user_role, user_sub, str(payload.employee_id)):
        raise EMSError(
            code="FORBIDDEN",
            message="Cannot create leave request for another employee",
            status_code=403,
        )

    # Validate employee with Employee Service (using Redis cache & fallback)
    emp_client: EmployeeClient = request.app.state.employee_client
    auth_header = authorization or ""
    emp_info = await emp_client.get_employee(str(payload.employee_id), auth_header)

    days = validate_leave_range(payload.start_date, payload.end_date)

    repo = LeaveRepository(session)
    # Check overlaps
    overlapping = await repo.find_overlapping_leaves(
        payload.employee_id, payload.start_date, payload.end_date
    )
    if overlapping:
        raise EMSError(
            code="LEAVE_OVERLAP",
            message="Leave request overlaps with an existing PENDING or APPROVED leave",
            status_code=409,
        )

    # For PAID leave, check balance
    if payload.leave_type == "PAID":
        used_days = await repo.sum_used_paid_days(payload.employee_id, payload.start_date.year)
        remaining = settings.ANNUAL_PAID_LEAVE_DAYS - used_days
        if days > remaining:
            raise EMSError(
                code="INSUFFICIENT_LEAVE_BALANCE",
                message=f"Requested {days} days exceeds remaining paid leave balance of {remaining}",
                status_code=422,
            )

    manager_id = UUID(emp_info["manager_id"]) if emp_info.get("manager_id") else None

    leave = Leave(
        employee_id=payload.employee_id,
        manager_id=manager_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        leave_type=payload.leave_type,
        reason=payload.reason,
        days=days,
        status="PENDING",
    )
    await repo.create_leave(leave)

    # Write outbox event
    event_payload = {
        "leave_id": str(leave.id),
        "employee_id": str(leave.employee_id),
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "leave_type": leave.leave_type,
        "days": leave.days,
    }
    add_outbox_event(
        session,
        event_type="LeaveRequested",
        payload=event_payload,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    return leave



@router.post("/leaves/{id}/approve", response_model=LeaveResponse)
async def approve_leave(
    id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    user_role = current_user["role"]
    user_sub = current_user["user_id"]

    if user_role not in ("MANAGER", "HR", "ADMIN"):
        raise EMSError(code="FORBIDDEN", message="Insufficient permissions", status_code=403)

    repo = LeaveRepository(session)
    leave = await repo.get_by_id_for_update(id)
    if not leave:
        raise EMSError(code="NOT_FOUND", message=f"Leave {id} not found", status_code=404)

    if str(leave.employee_id) == user_sub:
        raise EMSError(
            code="FORBIDDEN", message="Cannot approve your own leave", status_code=403
        )

    manager_id_str = str(leave.manager_id) if leave.manager_id else None
    if not can_decide_leave(user_role, user_sub, str(leave.employee_id), manager_id_str):
        raise EMSError(
            code="FORBIDDEN", message="Not authorized to approve this leave", status_code=403
        )

    LeaveStateMachine.validate_transition(leave.status, "APPROVED")

    if leave.leave_type == "PAID":
        used_days = await repo.sum_used_paid_days(leave.employee_id, leave.start_date.year)
        remaining = settings.ANNUAL_PAID_LEAVE_DAYS - used_days
        if leave.days > remaining:
            raise EMSError(
                code="INSUFFICIENT_LEAVE_BALANCE",
                message=f"Insufficient balance ({remaining} days remaining)",
                status_code=409,
            )

    leave.status = "APPROVED"
    leave.decided_by = UUID(user_sub)

    event_payload = {
        "leave_id": str(leave.id),
        "employee_id": str(leave.employee_id),
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "leave_type": leave.leave_type,
        "days": leave.days,
    }
    add_outbox_event(
        session,
        event_type="LeaveApproved",
        payload=event_payload,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    return leave


@router.post("/leaves/{id}/reject", response_model=LeaveResponse)
async def reject_leave(
    id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    user_role = current_user["role"]
    user_sub = current_user["user_id"]

    if user_role not in ("MANAGER", "HR", "ADMIN"):
        raise EMSError(code="FORBIDDEN", message="Insufficient permissions", status_code=403)

    repo = LeaveRepository(session)
    leave = await repo.get_by_id_for_update(id)
    if not leave:
        raise EMSError(code="NOT_FOUND", message=f"Leave {id} not found", status_code=404)

    if str(leave.employee_id) == user_sub:
        raise EMSError(
            code="FORBIDDEN", message="Cannot reject your own leave", status_code=403
        )

    manager_id_str = str(leave.manager_id) if leave.manager_id else None
    if not can_decide_leave(user_role, user_sub, str(leave.employee_id), manager_id_str):
        raise EMSError(
            code="FORBIDDEN", message="Not authorized to reject this leave", status_code=403
        )

    LeaveStateMachine.validate_transition(leave.status, "REJECTED")

    leave.status = "REJECTED"
    leave.decided_by = UUID(user_sub)

    event_payload = {
        "leave_id": str(leave.id),
        "employee_id": str(leave.employee_id),
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "leave_type": leave.leave_type,
        "days": leave.days,
    }
    add_outbox_event(
        session,
        event_type="LeaveRejected",
        payload=event_payload,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    return leave


@router.post("/leaves/{id}/cancel", response_model=LeaveResponse)
async def cancel_leave(
    id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    user_role = current_user["role"]
    user_sub = current_user["user_id"]

    repo = LeaveRepository(session)
    leave = await repo.get_by_id_for_update(id)
    if not leave:
        raise EMSError(code="NOT_FOUND", message=f"Leave {id} not found", status_code=404)

    if not can_cancel_leave(user_role, user_sub, str(leave.employee_id)):
        raise EMSError(
            code="FORBIDDEN", message="Not authorized to cancel this leave", status_code=403
        )

    old_status = leave.status
    LeaveStateMachine.validate_transition(old_status, "CANCELLED")

    leave.status = "CANCELLED"

    if old_status == "APPROVED":
        event_payload = {
            "leave_id": str(leave.id),
            "employee_id": str(leave.employee_id),
            "start_date": leave.start_date.isoformat(),
            "end_date": leave.end_date.isoformat(),
            "leave_type": leave.leave_type,
            "days": leave.days,
        }
        add_outbox_event(
            session,
            event_type="LeaveCancelled",
            payload=event_payload,
            correlation_id=get_correlation_id(),
        )

    await session.commit()
    return leave



@router.get("/leaves", response_model=LeaveListResponse)
async def list_leaves(
    employee_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    user_role = current_user["role"]
    user_sub = UUID(current_user["user_id"]) if current_user["user_id"] else None

    repo = LeaveRepository(session)
    items, total = await repo.list_leaves(
        employee_id=employee_id,
        status=status_filter,
        user_role=user_role,
        user_sub=user_sub,
        page=page,
        page_size=page_size,
    )
    return LeaveListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/leaves/balance/{employee_id}", response_model=LeaveBalanceResponse)
async def get_leave_balance(
    employee_id: UUID,
    year: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    user_role = current_user["role"]
    user_sub = current_user["user_id"]

    if not can_view_balance(user_role, user_sub, str(employee_id)):
        raise EMSError(
            code="FORBIDDEN",
            message="Cannot view leave balance of another employee",
            status_code=403,
        )

    target_year = year or datetime.now(timezone.utc).year
    repo = LeaveRepository(session)
    used = await repo.sum_used_paid_days(employee_id, target_year)
    bal = calculate_balance(settings.ANNUAL_PAID_LEAVE_DAYS, used)

    return LeaveBalanceResponse(
        employee_id=employee_id,
        year=target_year,
        allowance=bal["allowance"],
        used=bal["used"],
        remaining=bal["remaining"],
    )
