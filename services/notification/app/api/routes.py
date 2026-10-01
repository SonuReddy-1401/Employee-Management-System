from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.errors import EMSError
from ems_common.security import get_current_user
from services.notification.app.repositories.notification_repo import NotificationRepository

router = APIRouter()


async def get_db(request: Request):
    async with request.app.state.db_factory() as session:
        yield session


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    return {"status": "ok"}


@router.get("/notifications/{employee_id}")
async def list_notifications(
    employee_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current_user.get("role", "")
    sub = current_user.get("user_id", "")

    if role not in ("HR", "ADMIN") and sub != str(employee_id):
        raise EMSError(
            code="FORBIDDEN",
            message="You can only view your own notifications",
            status_code=403,
        )

    repo = NotificationRepository(db)
    notifications = await repo.list_by_employee(employee_id, limit=limit)
    return [
        {
            "id": str(n.id),
            "employee_id": str(n.employee_id),
            "event_id": str(n.event_id),
            "event_type": n.event_type,
            "message": n.message,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]
