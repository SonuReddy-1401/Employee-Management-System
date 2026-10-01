import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
import aio_pika
from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from ems_common.config import settings
from ems_common.correlation import get_correlation_id


class OutboxBase(DeclarativeBase):
    pass


class OutboxMessage(OutboxBase):
    __tablename__ = "outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def add_outbox_event(
    session: Session,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> OutboxMessage:
    corr_id = correlation_id or get_correlation_id()
    msg = OutboxMessage(
        event_type=event_type,
        payload=json.dumps(payload),
        correlation_id=corr_id,
    )
    session.add(msg)
    return msg


async def publish_outbox_messages(db_session: AsyncSession) -> int:
    stmt = select(OutboxMessage).where(OutboxMessage.published_at.is_(None)).order_by(OutboxMessage.created_at)
    result = await db_session.execute(stmt)
    messages = result.scalars().all()

    if not messages:
        return 0

    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )

        count = 0
        for msg in messages:
            envelope = {
                "event_id": msg.id,
                "type": msg.event_type,
                "occurred_at": msg.created_at.isoformat(),
                "correlation_id": msg.correlation_id,
                "payload": json.loads(msg.payload),
            }
            message = aio_pika.Message(
                body=json.dumps(envelope).encode("utf-8"),
                headers={"X-Correlation-ID": msg.correlation_id or ""},
            )
            await exchange.publish(message, routing_key=msg.event_type)
            msg.published_at = datetime.now(timezone.utc)
            count += 1

        await db_session.commit()
        return count
