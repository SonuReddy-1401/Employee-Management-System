import asyncio
import json
import os
import uuid
import aio_pika
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from ems_common.outbox import OutboxBase, OutboxMessage, publish_outbox_messages

from services.leave.app.main import outbox_publisher_loop


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
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_leave_real_outbox_publisher_loop(async_db_engine, rabbitmq_url, monkeypatch):
    import ems_common.config as config_mod
    import ems_common.outbox as outbox_mod
    import services.leave.app.config as leave_config_mod
    monkeypatch.setattr(config_mod.settings, "RABBITMQ_URL", rabbitmq_url)
    monkeypatch.setattr(outbox_mod.settings, "RABBITMQ_URL", rabbitmq_url)
    monkeypatch.setattr(leave_config_mod.settings, "RABBITMQ_URL", rabbitmq_url)



    session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)

    leave_id = str(uuid.uuid4())
    emp_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())
    payload = {
        "leave_id": leave_id,
        "employee_id": emp_id,
        "start_date": "2027-03-01",
        "end_date": "2027-03-03",
        "leave_type": "UNPAID",
        "days": 3,
    }

    # Insert an outbox message into the Leave outbox table
    async with session_factory() as session:
        msg = OutboxMessage(
            event_type="LeaveApproved",
            payload=json.dumps(payload),
            correlation_id=corr_id,
        )
        session.add(msg)
        await session.commit()
        msg_id = msg.id

    # Declare queue bound to ems.events exchange
    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue("test.leave.outbox.queue", durable=True)
        await queue.bind(exchange, routing_key="LeaveApproved")

        # Start the REAL outbox_publisher_loop from services.leave.app.main
        publisher_task = asyncio.create_task(
            outbox_publisher_loop(session_factory, poll_interval=0.2)
        )
        await asyncio.sleep(0.5)



        try:
            # Wait for message to arrive on bound queue with correct routing key
            incoming = await queue.get(timeout=10.0)
            await incoming.ack()

            body = json.loads(incoming.body.decode("utf-8"))
            assert body["event_id"] == msg_id
            assert body["type"] == "LeaveApproved"
            assert body["correlation_id"] == corr_id
            assert body["payload"]["leave_id"] == leave_id
        finally:
            publisher_task.cancel()
            try:
                await publisher_task
            except (Exception, asyncio.CancelledError):
                pass


    # Verify published_at is updated in DB
    async with session_factory() as session:
        stmt = select(OutboxMessage).where(OutboxMessage.id == msg_id)
        res = await session.execute(stmt)
        refreshed_msg = res.scalar_one_or_none()
        assert refreshed_msg is not None
        assert refreshed_msg.published_at is not None
