import os
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:
    from testcontainers.community.postgres import PostgresContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from ems_common.outbox import OutboxMessage
from services.employee.app.config import settings
from services.employee.app.main import app

settings.OUTBOX_PUBLISHER_ENABLED = False


@pytest.mark.asyncio
async def test_fresh_database_startup_and_onboarding():
    with PostgresContainer("postgres:16-alpine") as postgres:
        connection_url = postgres.get_connection_url()
        async_url = connection_url.replace("postgresql://", "postgresql+asyncpg://").replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

        settings.DATABASE_URL = async_url

        import services.employee.app.main as emp_main
        from services.employee.app.api.routes import get_db
        emp_main.engine = create_async_engine(async_url, poolclass=NullPool, echo=False)
        emp_main.async_session_factory = async_sessionmaker(emp_main.engine, class_=AsyncSession, expire_on_commit=False)
        app.dependency_overrides[get_db] = emp_main.get_db_override


        async with app.router.lifespan_context(app):
            # 1. Assert tables 'employees' and 'outbox' both exist in information_schema
            async with emp_main.async_session_factory() as session:
                result = await session.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
                tables = {row[0] for row in result.fetchall()}
                assert "employees" in tables, f"Expected 'employees' table in {tables}"
                assert "outbox" in tables, f"Expected 'outbox' table in {tables}"

            # 2. Run a successful onboarding with respx mocks for Auth and Payroll
            auth_url = f"{settings.AUTH_SERVICE_URL}/internal/users"
            payroll_url = f"{settings.PAYROLL_SERVICE_URL}/internal/profiles"

            with respx.mock(assert_all_called=False) as respx_mock:
                respx_mock.post(auth_url).respond(status_code=201, json={"id": "user-123", "email": "fresh@example.com"})
                respx_mock.post(payroll_url).respond(status_code=201, json={"id": "prof-123"})

                import jwt
                from datetime import datetime, timedelta, timezone
                token_payload = {
                    "sub": "admin-123",
                    "role": "ADMIN",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                }
                token = jwt.encode(token_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
                headers = {"Authorization": f"Bearer {token}"}

                payload = {
                    "name": "Fresh User",
                    "email": "fresh@example.com",
                    "department": "Engineering",
                    "designation": "Software Engineer",
                    "initial_password": "password123",
                    "monthly_salary": 5000.0,
                }

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post("/employees", json=payload, headers=headers)
                    assert response.status_code == 201
                    data = response.json()
                    assert data["status"] == "ACTIVE"

            # 3. Assert exactly one outbox row exists
            async with emp_main.async_session_factory() as session:
                outbox_res = await session.execute(select(OutboxMessage))
                outbox_rows = outbox_res.scalars().all()
                assert len(outbox_rows) == 1, f"Expected 1 outbox row, found {len(outbox_rows)}"
                assert outbox_rows[0].event_type == "EmployeeOnboarded"

