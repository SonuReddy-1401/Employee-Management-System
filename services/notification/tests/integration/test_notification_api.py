import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from ems_common.events import EventEnvelope, EventType
from services.notification.app.api.routes import get_db
from services.notification.app.config import settings
from services.notification.app.consumer_handler import handle_notification_event
from services.notification.app.main import app
from services.notification.app.models.notification import Base, ConsumerBase, Notification


@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest_asyncio.fixture(scope="module")
async def setup_db_and_app(postgres_container):
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )

    settings.DATABASE_URL = async_url
    settings.CONSUMER_ENABLED = False

    engine = create_async_engine(async_url, poolclass=NullPool, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ConsumerBase.metadata.create_all)

    async def get_test_db():
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = get_test_db
    app.state.db_factory = async_session_factory

    yield async_session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def jwt_secret():
    return settings.JWT_SECRET


def create_token(sub: str, role: str, secret: str) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_health_and_metrics(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = await ac.get("/health")
        assert r1.status_code == 200
        assert r1.json() == {"status": "ok"}

        r2 = await ac.get("/metrics")
        assert r2.status_code == 200


@pytest.mark.asyncio
async def test_consumer_handler_creates_and_skips_duplicates(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = uuid4()
    event_id = uuid4()

    envelope = EventEnvelope(
        event_id=event_id,
        type=EventType.EMPLOYEE_ONBOARDED,
        correlation_id=uuid4(),
        payload={"employee_id": str(emp_id), "name": "Bob Smith"},
    )

    async with session_factory() as session:
        await handle_notification_event(session, envelope)
        await session.commit()

    # Verify notification created
    async with session_factory() as session:
        from services.notification.app.repositories.notification_repo import NotificationRepository
        repo = NotificationRepository(session)
        notifs = await repo.list_by_employee(emp_id)
        assert len(notifs) == 1
        assert notifs[0].event_id == event_id
        assert notifs[0].message == "Welcome Bob Smith, your account is ready."

    # Call handler second time with SAME event_id
    async with session_factory() as session:
        await handle_notification_event(session, envelope)
        await session.commit()

    # Verify still only 1 notification
    async with session_factory() as session:
        repo = NotificationRepository(session)
        notifs = await repo.list_by_employee(emp_id)
        assert len(notifs) == 1


@pytest.mark.asyncio
async def test_list_notifications_permissions(setup_db_and_app, jwt_secret):
    session_factory = setup_db_and_app
    emp1_id = uuid4()
    emp2_id = uuid4()

    # Populate notification for emp1
    envelope = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "employee_id": str(emp1_id),
            "leave_type": "ANNUAL",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "days": 5,
        },
    )
    async with session_factory() as session:
        await handle_notification_event(session, envelope)
        await session.commit()

    token_emp1 = create_token(str(emp1_id), "EMPLOYEE", jwt_secret)
    token_emp2 = create_token(str(emp2_id), "EMPLOYEE", jwt_secret)
    token_hr = create_token(str(uuid4()), "HR", jwt_secret)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Read own as emp1 -> 200
        r1 = await ac.get(f"/notifications/{emp1_id}", headers={"Authorization": f"Bearer {token_emp1}"})
        assert r1.status_code == 200
        data1 = r1.json()
        assert len(data1) >= 1
        assert data1[0]["employee_id"] == str(emp1_id)

        # 2. Read emp1 as emp2 -> 403
        r2 = await ac.get(f"/notifications/{emp1_id}", headers={"Authorization": f"Bearer {token_emp2}"})
        assert r2.status_code == 403
        assert r2.json()["error"]["code"] == "FORBIDDEN"

        # 3. Read emp1 as HR -> 200
        r3 = await ac.get(f"/notifications/{emp1_id}", headers={"Authorization": f"Bearer {token_hr}"})
        assert r3.status_code == 200

        # 4. Missing token -> 401
        r4 = await ac.get(f"/notifications/{emp1_id}")
        assert r4.status_code == 401


@pytest.mark.asyncio
async def test_n4_list_notifications_limit_and_descending_order(setup_db_and_app, jwt_secret):
    import asyncio
    session_factory = setup_db_and_app
    emp_id = uuid4()

    # Create 3 notifications sequentially with small delay
    for i in range(3):
        envelope = EventEnvelope(
            event_id=uuid4(),
            type=EventType.EMPLOYEE_ONBOARDED,
            correlation_id=uuid4(),
            payload={"employee_id": str(emp_id), "name": f"User {i}"},
        )
        async with session_factory() as session:
            await handle_notification_event(session, envelope)
            await session.commit()
        await asyncio.sleep(0.01)

    token = create_token(str(emp_id), "EMPLOYEE", jwt_secret)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test limit parameter
        res_limit = await ac.get(f"/notifications/{emp_id}?limit=2", headers={"Authorization": f"Bearer {token}"})
        assert res_limit.status_code == 200
        items = res_limit.json()
        assert len(items) == 2

        # Verify descending order (most recent first)
        res_all = await ac.get(f"/notifications/{emp_id}?limit=50", headers={"Authorization": f"Bearer {token}"})
        assert res_all.status_code == 200
        all_items = res_all.json()
        assert len(all_items) >= 3
        # Compare created_at timestamps
        t0 = datetime.fromisoformat(all_items[0]["created_at"])
        t1 = datetime.fromisoformat(all_items[1]["created_at"])
        assert t0 >= t1


@pytest.fixture(scope="module")
def rabbitmq_container():
    from testcontainers.core.container import DockerContainer
    with DockerContainer("rabbitmq:3-management-alpine").with_exposed_ports(5672) as rabbitmq:
        yield rabbitmq


@pytest_asyncio.fixture(scope="module")
async def rabbitmq_url(rabbitmq_container):
    import asyncio
    import aio_pika
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


@pytest.mark.asyncio
async def test_n6_e2e_rabbitmq_notification_consumer(setup_db_and_app, rabbitmq_url):
    import asyncio
    import aio_pika
    from ems_common.consumer import run_consumer
    from services.notification.app.repositories.notification_repo import NotificationRepository

    session_factory = setup_db_and_app
    emp_id = uuid4()
    event_id = uuid4()

    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(
        run_consumer(
            rabbitmq_url=rabbitmq_url,
            exchange_name="ems.events",
            queue_name="notification.e2e.test.queue",
            dlx_name="notification.e2e.test.dlx",
            dlq_name="notification.e2e.test.dlq",
            routing_keys=["EmployeeOnboarded"],
            session_factory=session_factory,
            handler=handle_notification_event,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.5)

    # Publish EmployeeOnboarded envelope to topic exchange
    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)

        envelope = EventEnvelope(
            event_id=event_id,
            type=EventType.EMPLOYEE_ONBOARDED,
            correlation_id=uuid4(),
            payload={"employee_id": str(emp_id), "name": "E2E Notification User"},
        )
        msg_bytes = envelope.model_dump_json().encode("utf-8")
        await exchange.publish(
            aio_pika.Message(body=msg_bytes, headers={"X-Correlation-ID": str(uuid4())}),
            routing_key="EmployeeOnboarded",
        )

    # Bounded wait loop (no fixed sleep)
    found = False
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < 10.0:
        async with session_factory() as session:
            repo = NotificationRepository(session)
            notifs = await repo.list_by_employee(emp_id)
            if len(notifs) >= 1:
                assert notifs[0].event_id == event_id
                assert "Welcome E2E Notification User" in notifs[0].message
                found = True
                break
        await asyncio.sleep(0.2)

    stop_event.set()
    consumer_task.cancel()
    try:
        await consumer_task
    except (Exception, asyncio.CancelledError):
        pass

    assert found is True
