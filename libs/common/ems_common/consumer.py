import logging
from datetime import datetime, timezone
from typing import Any, Callable
from sqlalchemy import DateTime, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from ems_common.config import settings

logger = logging.getLogger(__name__)


class ConsumerBase(DeclarativeBase):
    pass


class ProcessedEvent(ConsumerBase):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def is_event_processed(session: Session, event_id: str) -> bool:
    stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
    return session.scalar(stmt) is not None


def mark_event_processed(session: Session, event_id: str) -> ProcessedEvent:
    entry = ProcessedEvent(event_id=event_id)
    session.add(entry)
    return entry


def process_idempotent_event(session: Session, event_id: str, handler: Callable[[], Any]) -> bool:
    if is_event_processed(session, event_id):
        logger.info(f"Event '{event_id}' has already been processed. Skipping execution.")
        return False

    attempts = 0
    max_attempts = settings.CONSUMER_MAX_ATTEMPTS

    while attempts < max_attempts:
        try:
            handler()
            mark_event_processed(session, event_id)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            attempts += 1
            logger.warning(
                f"Attempt {attempts}/{max_attempts} failed for event '{event_id}': {e}"
            )
            if attempts >= max_attempts:
                logger.error(
                    f"Max attempts ({max_attempts}) reached for event '{event_id}'. Routing to DLQ '{settings.CONSUMER_DLQ_NAME}'."
                )
                raise e
    return False
