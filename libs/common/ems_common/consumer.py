import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional
import aio_pika
from pydantic import ValidationError
from sqlalchemy import DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from ems_common.config import settings
from ems_common.events import EventEnvelope

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


async def async_is_event_processed(session: AsyncSession, event_id: str) -> bool:
    stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None


async def async_mark_event_processed(session: AsyncSession, event_id: str) -> ProcessedEvent:
    entry = ProcessedEvent(event_id=event_id)
    session.add(entry)
    return entry


async def run_consumer(
    rabbitmq_url: str,
    exchange_name: str,
    queue_name: str,
    dlx_name: str,
    dlq_name: str,
    routing_keys: List[str],
    session_factory: Callable[[], AsyncSession],
    handler: Callable[[AsyncSession, EventEnvelope], Any],
    max_attempts: Optional[int] = None,
    stop_event: Optional[asyncio.Event] = None,
):
    attempts_limit = max_attempts if max_attempts is not None else settings.CONSUMER_MAX_ATTEMPTS

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        # Declare topic exchange
        exchange = await channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

        # Declare dead letter exchange & queue
        dlx = await channel.declare_exchange(
            dlx_name, aio_pika.ExchangeType.DIRECT, durable=True
        )
        dlq = await channel.declare_queue(dlq_name, durable=True)
        await dlq.bind(dlx, routing_key=dlq_name)

        # Declare main durable queue with DLX settings
        main_queue = await channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": dlx_name,
                "x-dead-letter-routing-key": dlq_name,
            },
        )

        for rkey in routing_keys:
            await main_queue.bind(exchange, routing_key=rkey)

        async with main_queue.iterator() as queue_iter:
            async for message in queue_iter:
                if stop_event and stop_event.is_set():
                    break

                # Check if body is valid EventEnvelope
                try:
                    raw_data = json.loads(message.body.decode("utf-8"))
                    envelope = EventEnvelope.model_validate(raw_data)
                except (json.JSONDecodeError, ValidationError, Exception) as parse_err:
                    logger.error(f"Malformed message received: {parse_err}. Rejecting to DLQ.")
                    await message.reject(requeue=False)
                    continue

                event_id_str = str(envelope.event_id)
                current_attempt = message.headers.get("x-delivery-attempt", 1) if message.headers else 1

                session = session_factory()
                try:
                    if await async_is_event_processed(session, event_id_str):
                        logger.info(f"Duplicate event '{event_id_str}' received. Skipping.")
                        await message.ack()
                        continue

                    try:
                        res = handler(session, envelope)
                        if asyncio.iscoroutine(res):
                            await res

                        await async_mark_event_processed(session, event_id_str)
                        await session.commit()
                        await message.ack()
                    except Exception as handler_err:
                        try:
                            await session.rollback()
                        except Exception:
                            pass
                        logger.warning(
                            f"Attempt {current_attempt}/{attempts_limit} failed for event '{event_id_str}': {handler_err}"
                        )
                        if current_attempt < attempts_limit:
                            new_headers = dict(message.headers or {})
                            new_headers["x-delivery-attempt"] = current_attempt + 1
                            retry_msg = aio_pika.Message(
                                body=message.body,
                                headers=new_headers,
                                correlation_id=message.correlation_id,
                            )
                            await exchange.publish(retry_msg, routing_key=message.routing_key or envelope.type.value)
                            await message.ack()
                        else:
                            logger.error(
                                f"Max attempts ({attempts_limit}) reached for event '{event_id_str}'. Sending to DLQ."
                            )
                            await message.reject(requeue=False)
                finally:
                    await session.close()
