import asyncio
import json
import socket
import time
import uuid
import aio_pika
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

from ems_common.consumer import ConsumerBase, ProcessedEvent, run_consumer
from ems_common.events import EventEnvelope, EventType
from ems_common.outbox import OutboxBase, add_outbox_event, publish_outbox_messages


@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="module")
def rabbitmq_container():
    with DockerContainer("rabbitmq:3-management-alpine").with_exposed_ports(5672) as rabbitmq:
        yield rabbitmq


@pytest_asyncio.fixture(scope="module")
async def rabbitmq_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    url = f"amqp://guest:guest@{host}:{port}/"

    for _ in range(30):
        try:
            conn = await aio_pika.connect_robust(url, timeout=2)
            await conn.close()
            break
        except Exception:
            await asyncio.sleep(1)
    return url


@pytest_asyncio.fixture(loop_scope="module")
async def async_db_engine(postgres_container):
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(async_url, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(OutboxBase.metadata.create_all)
        await conn.run_sync(ConsumerBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_outbox_publish_to_broker(async_db_engine, rabbitmq_url, monkeypatch):
    import ems_common.outbox as outbox_mod
    monkeypatch.setattr(outbox_mod.settings, "RABBITMQ_URL", rabbitmq_url)

    async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)

    payload = {"employee_id": str(uuid.uuid4()), "name": "John Doe"}
    corr_id = str(uuid.uuid4())

    msg_id = None
    async with async_session_factory() as session:
        msg = outbox_mod.OutboxMessage(
            event_type="EmployeeOnboarded",
            payload=json.dumps(payload),
            correlation_id=corr_id,
        )
        session.add(msg)
        await session.commit()
        msg_id = msg.id

    # Declare a test queue bound to ems.events topic exchange
    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue("test.outbox.queue", durable=True)
        await queue.bind(exchange, routing_key="EmployeeOnboarded")

        # Publish outbox messages
        async with async_session_factory() as async_sess:
            count = await publish_outbox_messages(async_sess)
            assert count >= 1

        # Read message from queue
        incoming = await queue.get(timeout=5)
        await incoming.ack()

        body = json.loads(incoming.body.decode("utf-8"))
        assert body["event_id"] == msg_id
        assert body["type"] == "EmployeeOnboarded"
        assert body["correlation_id"] == corr_id
        assert body["payload"]["name"] == "John Doe"

    # Verify published_at is set in DB
    async with async_session_factory() as session:
        stmt = outbox_mod.select(outbox_mod.OutboxMessage).where(outbox_mod.OutboxMessage.id == msg_id)
        res = await session.execute(stmt)
        refreshed_msg = res.scalar_one_or_none()
        assert refreshed_msg is not None
        assert refreshed_msg.published_at is not None


@pytest.mark.asyncio
async def test_run_consumer_ack(async_db_engine, rabbitmq_url):
    async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
    handler_called = asyncio.Event()
    event_id = uuid.uuid4()
    corr_id = uuid.uuid4()

    async def mock_handler(session, envelope):
        if envelope.event_id == event_id:
            handler_called.set()

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_consumer(
            rabbitmq_url=rabbitmq_url,
            exchange_name="ems.events",
            queue_name="test.consumer.queue",
            dlx_name="test.consumer.dlx",
            dlq_name="test.consumer.dlq",
            routing_keys=["EmployeeOnboarded"],
            session_factory=async_session_factory,
            handler=mock_handler,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.5)

    # Publish message directly to exchange
    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        envelope = EventEnvelope(
            event_id=event_id,
            type=EventType.EMPLOYEE_ONBOARDED,
            correlation_id=corr_id,
            payload={"employee_id": str(uuid.uuid4())},
        )
        msg = aio_pika.Message(body=envelope.model_dump_json().encode("utf-8"))
        await exchange.publish(msg, routing_key="EmployeeOnboarded")

    await asyncio.wait_for(handler_called.wait(), timeout=5.0)

    stop_event.set()
    task.cancel()
    try:
        await task
    except (Exception, asyncio.CancelledError):
        pass

    assert handler_called.is_set()


@pytest.mark.asyncio
async def test_run_consumer_idempotency(async_db_engine, rabbitmq_url):
    async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
    call_count = 0
    event_id = uuid.uuid4()
    corr_id = uuid.uuid4()

    async def mock_handler(session, envelope):
        nonlocal call_count
        if envelope.event_id == event_id:
            call_count += 1

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_consumer(
            rabbitmq_url=rabbitmq_url,
            exchange_name="ems.events",
            queue_name="test.idempotency.queue",
            dlx_name="test.idempotency.dlx",
            dlq_name="test.idempotency.dlq",
            routing_keys=["EmployeeOnboarded"],
            session_factory=async_session_factory,
            handler=mock_handler,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.5)

    # Publish SAME event_id twice
    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        envelope = EventEnvelope(
            event_id=event_id,
            type=EventType.EMPLOYEE_ONBOARDED,
            correlation_id=corr_id,
            payload={"employee_id": str(uuid.uuid4())},
        )
        msg_bytes = envelope.model_dump_json().encode("utf-8")
        await exchange.publish(aio_pika.Message(body=msg_bytes), routing_key="EmployeeOnboarded")
        await exchange.publish(aio_pika.Message(body=msg_bytes), routing_key="EmployeeOnboarded")

    await asyncio.sleep(1.5)
    stop_event.set()
    task.cancel()
    try:
        await task
    except (Exception, asyncio.CancelledError):
        pass

    assert call_count == 1


@pytest.mark.asyncio
async def test_run_consumer_retries_to_dlq(async_db_engine, rabbitmq_url):
    async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
    attempts_made = 0
    event_id = uuid.uuid4()

    async def failing_handler(session, envelope):
        nonlocal attempts_made
        if envelope.event_id == event_id:
            attempts_made += 1
            raise ValueError("Simulated handler failure")

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_consumer(
            rabbitmq_url=rabbitmq_url,
            exchange_name="ems.events",
            queue_name="test.retry.queue",
            dlx_name="test.retry.dlx",
            dlq_name="test.retry.dlq",
            routing_keys=["EmployeeOnboarded"],
            session_factory=async_session_factory,
            handler=failing_handler,
            max_attempts=3,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.5)

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        envelope = EventEnvelope(
            event_id=event_id,
            type=EventType.EMPLOYEE_ONBOARDED,
            correlation_id=uuid.uuid4(),
            payload={"employee_id": str(uuid.uuid4())},
        )
        await exchange.publish(
            aio_pika.Message(body=envelope.model_dump_json().encode("utf-8")),
            routing_key="EmployeeOnboarded",
        )

    await asyncio.sleep(2.5)
    stop_event.set()
    task.cancel()
    try:
        await task
    except (Exception, asyncio.CancelledError):
        pass

    assert attempts_made == 3

    # Check that message landed in DLQ
    connection2 = await aio_pika.connect_robust(rabbitmq_url)
    async with connection2:
        channel = await connection2.channel()
        dlq = await channel.declare_queue("test.retry.dlq", durable=True)
        dlq_msg = await dlq.get(timeout=3)
        assert dlq_msg is not None
        await dlq_msg.ack()


@pytest.mark.asyncio
async def test_run_consumer_malformed_to_dlq(async_db_engine, rabbitmq_url):
    async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
    handler_called = False

    async def dummy_handler(session, envelope):
        nonlocal handler_called
        handler_called = True

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_consumer(
            rabbitmq_url=rabbitmq_url,
            exchange_name="ems.events",
            queue_name="test.malformed.queue",
            dlx_name="test.malformed.dlx",
            dlq_name="test.malformed.dlq",
            routing_keys=["EmployeeOnboarded"],
            session_factory=async_session_factory,
            handler=dummy_handler,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.5)

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        # Publish malformed JSON
        await exchange.publish(
            aio_pika.Message(body=b"{invalid_json: true}"),
            routing_key="EmployeeOnboarded",
        )

    await asyncio.sleep(1.5)
    stop_event.set()
    task.cancel()
    try:
        await task
    except (Exception, asyncio.CancelledError):
        pass

    assert handler_called is False

    # Check DLQ immediately got the malformed message
    connection2 = await aio_pika.connect_robust(rabbitmq_url)
    async with connection2:
        channel = await connection2.channel()
        dlq = await channel.declare_queue("test.malformed.dlq", durable=True)
        dlq_msg = await dlq.get(timeout=3)
        assert dlq_msg is not None
        assert dlq_msg.body == b"{invalid_json: true}"
        await dlq_msg.ack()
