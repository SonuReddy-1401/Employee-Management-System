import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.events import EventEnvelope
from services.notification.app.domain.notification import build_notification
from services.notification.app.models.notification import Notification
from services.notification.app.repositories.notification_repo import NotificationRepository

logger = logging.getLogger(__name__)


async def handle_notification_event(session: AsyncSession, envelope: EventEnvelope) -> None:
    repo = NotificationRepository(session)
    existing = await repo.get_by_event_id(envelope.event_id)
    if existing:
        logger.info(f"Notification for event_id {envelope.event_id} already exists. Skipping.")
        return

    emp_id, message = build_notification(envelope)
    notification = Notification(
        employee_id=emp_id,
        event_id=envelope.event_id,
        event_type=envelope.type.value,
        message=message,
    )
    session.add(notification)
    logger.info(f"SIMULATED EMAIL to employee {emp_id}: {message}")
