from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.notification.app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(self, notification: Notification) -> Notification:
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def get_by_event_id(self, event_id: UUID) -> Optional[Notification]:
        stmt = select(Notification).where(Notification.event_id == event_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_employee(self, employee_id: UUID, limit: int = 50) -> List[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.employee_id == employee_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
