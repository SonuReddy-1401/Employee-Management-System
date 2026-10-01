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
