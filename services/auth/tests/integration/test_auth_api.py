import os
from uuid import uuid4
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:
    from testcontainers.community.postgres import PostgresContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from services.auth.app.api.routes import get_db
from services.auth.app.config import settings
from services.auth.app.main import app, seed_admin
from services.auth.app.models.user import Base


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
    settings.ADMIN_EMAIL = "admin@example.com"
    settings.ADMIN_PASSWORD = "adminpassword123"

    engine = create_async_engine(async_url, poolclass=NullPool, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await seed_admin(session)

    async def get_test_db():
        async with async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = get_test_db

    yield

    await engine.dispose()


@pytest.mark.asyncio
async def test_health_and_metrics_endpoints(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json() == {"status": "ok"}

        res_metrics = await client.get("/metrics")
        assert res_metrics.status_code == 200
        assert "process_cpu_seconds_total" in res_metrics.text or "python_gc_objects_collected_total" in res_metrics.text or "# HELP" in res_metrics.text


@pytest.mark.asyncio
async def test_seeded_admin_login(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"email": "admin@example.com", "password": "adminpassword123"}
        res = await client.post("/auth/login", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        decoded = jwt.decode(data["access_token"], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert decoded["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_login_wrong_password(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"email": "admin@example.com", "password": "wrongpassword"}
        res = await client.post("/auth/login", json=payload)
        assert res.status_code == 401
        assert res.json() == {"error": {"code": "UNAUTHORIZED", "message": "Invalid email or password"}}


@pytest.mark.asyncio
async def test_login_unknown_email(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"email": "nonexistent@example.com", "password": "anypassword"}
        res = await client.post("/auth/login", json=payload)
        assert res.status_code == 401
        assert res.json() == {"error": {"code": "UNAUTHORIZED", "message": "Invalid email or password"}}


@pytest.mark.asyncio
async def test_create_user_success_and_login(setup_db_and_app):
    user_id = str(uuid4())
    user_email = f"emp_{user_id[:8]}@example.com"
    user_pass = "EmployeePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_payload = {
            "id": user_id,
            "email": user_email,
            "password": user_pass,
            "role": "EMPLOYEE",
        }
        res_create = await client.post("/internal/users", json=create_payload)
        assert res_create.status_code == 201
        created_data = res_create.json()
        assert created_data["id"] == user_id
        assert created_data["email"] == user_email
        assert created_data["role"] == "EMPLOYEE"
        assert "password_hash" not in created_data

        # Verify new user can log in
        login_payload = {"email": user_email, "password": user_pass}
        res_login = await client.post("/auth/login", json=login_payload)
        assert res_login.status_code == 200
        token_data = res_login.json()
        decoded = jwt.decode(token_data["access_token"], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert decoded["sub"] == user_id
        assert decoded["role"] == "EMPLOYEE"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(setup_db_and_app):
    user_id_1 = str(uuid4())
    user_id_2 = str(uuid4())
    dup_email = f"dup_{user_id_1[:8]}@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create first
        res1 = await client.post(
            "/internal/users",
            json={"id": user_id_1, "email": dup_email, "password": "password123", "role": "HR"},
        )
        assert res1.status_code == 201

        # Attempt duplicate email
        res2 = await client.post(
            "/internal/users",
            json={"id": user_id_2, "email": dup_email, "password": "password123", "role": "HR"},
        )
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_user_duplicate_id(setup_db_and_app):
    user_id = str(uuid4())
    email1 = f"e1_{user_id[:8]}@example.com"
    email2 = f"e2_{user_id[:8]}@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create first
        res1 = await client.post(
            "/internal/users",
            json={"id": user_id, "email": email1, "password": "password123", "role": "MANAGER"},
        )
        assert res1.status_code == 201

        # Attempt duplicate ID
        res2 = await client.post(
            "/internal/users",
            json={"id": user_id, "email": email2, "password": "password123", "role": "MANAGER"},
        )
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_user_invalid_role(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/internal/users",
            json={
                "id": str(uuid4()),
                "email": "invalid_role@example.com",
                "password": "password123",
                "role": "SUPERADMIN",
            },
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_user_short_password(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/internal/users",
            json={
                "id": str(uuid4()),
                "email": "short_pass@example.com",
                "password": "short",
                "role": "EMPLOYEE",
            },
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_delete_user_success_and_idempotency(setup_db_and_app):
    user_id = str(uuid4())
    user_email = f"del_{user_id[:8]}@example.com"
    user_pass = "PasswordToDel123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create user
        res_create = await client.post(
            "/internal/users",
            json={"id": user_id, "email": user_email, "password": user_pass, "role": "EMPLOYEE"},
        )
        assert res_create.status_code == 201

        # Delete user -> 204
        res_del1 = await client.delete(f"/internal/users/{user_id}")
        assert res_del1.status_code == 204

        # Delete user again -> 204 (idempotent)
        res_del2 = await client.delete(f"/internal/users/{user_id}")
        assert res_del2.status_code == 204

        # Login attempt should fail with 401
        res_login = await client.post(
            "/auth/login", json={"email": user_email, "password": user_pass}
        )
        assert res_login.status_code == 401
