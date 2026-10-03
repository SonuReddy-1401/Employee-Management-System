import asyncio
import logging
import time
import uuid
import aio_pika
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

from ems_common.consumer import ConsumerBase, run_consumer
from ems_common.events import EventEnvelope, EventType
from ems_common.outbox import OutboxBase


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
async def test_retries_while_broker_unreachable(monkeypatch):
    """T1: Retries while broker unreachable with exponential backoff."""
    async def _test():
        call_times = []

        class DummyChannel:
            async def set_qos(self, prefetch_count):
                pass

            async def declare_exchange(self, name, type, durable=True):
                return DummyExchange()

            async def declare_queue(self, name, durable=True, arguments=None):
                return DummyQueue()

        class DummyExchange:
            pass

        class DummyQueue:
            async def bind(self, exchange, routing_key):
                pass

            def iterator(self):
                return DummyQueueIterator()

        class DummyQueueIterator:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def __anext__(self):
                await asyncio.sleep(10)
                raise StopAsyncIteration

        class DummyConnection:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def channel(self):
                return DummyChannel()

        dummy_conn = DummyConnection()

        async def mock_connect(*args, **kwargs):
            call_times.append(time.time())
            if len(call_times) <= 3:
                raise ConnectionError("Broker unreachable")
            return dummy_conn

        monkeypatch.setattr(aio_pika, "connect_robust", mock_connect)

        stop_event = asyncio.Event()

        consumer_task = asyncio.create_task(
            run_consumer(
                rabbitmq_url="amqp://guest:guest@localhost:5672/",
                exchange_name="test.ex",
                queue_name="test.q",
                dlx_name="test.dlx",
                dlq_name="test.dlq",
                routing_keys=["test.key"],
                session_factory=lambda: None,
                handler=lambda s, e: None,
                stop_event=stop_event,
                initial_reconnect_delay=0.1,
                max_reconnect_delay=0.5,
                connect_timeout=0.5,
                stop_poll_seconds=0.1,
            )
        )

        try:
            for _ in range(100):
                if len(call_times) >= 4:
                    break
                await asyncio.sleep(0.05)

            assert not consumer_task.done(), "Consumer task stopped prematurely during retries"
            assert len(call_times) >= 4, f"Expected at least 4 connect attempts, got {len(call_times)}"

            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            delay3 = call_times[3] - call_times[2]
            assert delay2 > delay1, f"Expected growing delay: delay1={delay1:.3f}, delay2={delay2:.3f}"
            assert delay3 > delay2, f"Expected growing delay: delay2={delay2:.3f}, delay3={delay3:.3f}"
        finally:
            stop_event.set()
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass

    await asyncio.wait_for(_test(), timeout=30.0)


@pytest.mark.asyncio
async def test_stop_event_ends_idle_consumer(async_db_engine, rabbitmq_url, caplog):
    """T2: Consumer ends within 3s when stop_event is set on an idle connected consumer."""
    async def _test():
        caplog.set_level(logging.INFO)
        async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
        stop_event = asyncio.Event()

        async def _dummy_handler(session, envelope):
            pass

        uid = uuid.uuid4().hex[:8]
        consumer_task = asyncio.create_task(
            run_consumer(
                rabbitmq_url=rabbitmq_url,
                exchange_name=f"test.ex.{uid}",
                queue_name=f"test.q.{uid}",
                dlx_name=f"test.dlx.{uid}",
                dlq_name=f"test.dlq.{uid}",
                routing_keys=["EmployeeOnboarded"],
                session_factory=async_session_factory,
                handler=_dummy_handler,
                stop_event=stop_event,
                stop_poll_seconds=0.5,
            )
        )

        try:
            connected = False
            for _ in range(60):
                if "Consumer connected" in caplog.text:
                    connected = True
                    break
                await asyncio.sleep(0.1)

            assert connected, "Consumer failed to log 'Consumer connected' within timeout"

            start_time = time.time()
            stop_event.set()

            await asyncio.wait_for(consumer_task, timeout=3.0)
            elapsed = time.time() - start_time
            assert elapsed <= 3.0, f"Task took {elapsed:.2f}s to stop, expected <= 3s"
        finally:
            stop_event.set()
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass

    await asyncio.wait_for(_test(), timeout=30.0)


@pytest.mark.asyncio
async def test_message_received_once_after_connect(async_db_engine, rabbitmq_url, caplog):
    """T3: Message published twice is processed exactly once by handler."""
    async def _test():
        caplog.set_level(logging.INFO)
        async_session_factory = async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
        call_count = 0
        event_id = uuid.uuid4()
        corr_id = uuid.uuid4()

        async def mock_handler(session, envelope):
            nonlocal call_count
            if envelope.event_id == event_id:
                call_count += 1

        stop_event = asyncio.Event()
        uid = uuid.uuid4().hex[:8]
        ex_name = f"ems.events.{uid}"
        q_name = f"test.idempotency.q.{uid}"
        dlx_name = f"test.idempotency.dlx.{uid}"
        dlq_name = f"test.idempotency.dlq.{uid}"

        consumer_task = asyncio.create_task(
            run_consumer(
                rabbitmq_url=rabbitmq_url,
                exchange_name=ex_name,
                queue_name=q_name,
                dlx_name=dlx_name,
                dlq_name=dlq_name,
                routing_keys=["EmployeeOnboarded"],
                session_factory=async_session_factory,
                handler=mock_handler,
                stop_event=stop_event,
                stop_poll_seconds=0.5,
            )
        )

        try:
            connected = False
            for _ in range(60):
                if "Consumer connected" in caplog.text:
                    connected = True
                    break
                await asyncio.sleep(0.1)
            assert connected, "Consumer failed to connect"

            pub_conn = await aio_pika.connect_robust(rabbitmq_url)
            async with pub_conn:
                channel = await pub_conn.channel()
                exchange = await channel.declare_exchange(ex_name, aio_pika.ExchangeType.TOPIC, durable=True)
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

            assert call_count == 1, f"Expected handler to run exactly once, ran {call_count} times"
        finally:
            stop_event.set()
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass

    await asyncio.wait_for(_test(), timeout=30.0)
