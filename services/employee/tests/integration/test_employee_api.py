import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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

from services.employee.app.api.routes import get_db
from services.employee.app.config import settings
from services.employee.app.main import app
from services.employee.app.models.employee import Base


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

    engine = create_async_engine(async_url, poolclass=NullPool, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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


def make_auth_headers(role: str = "HR", user_id: str = None) -> dict:
    uid = user_id or str(uuid4())
    payload = {
        "sub": uid,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_and_metrics_endpoints(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json() == {"status": "ok"}

        res_metrics = await client.get("/metrics")
        assert res_metrics.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_and_forbidden_access(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No token -> 401
        res_no_token = await client.get("/employees")
        assert res_no_token.status_code == 401
        assert res_no_token.json()["error"]["code"] == "UNAUTHORIZED"

        # EMPLOYEE role cannot create -> 403
        emp_headers = make_auth_headers(role="EMPLOYEE")
        payload = {
            "name": "Jane",
            "email": "jane@example.com",
            "department": "Sales",
            "designation": "Executive",
            "initial_password": "Password123!",
            "monthly_salary": 4500.00,
        }
        res_create_emp = await client.post("/employees", json=payload, headers=emp_headers)
        assert res_create_emp.status_code == 403
        assert res_create_emp.json()["error"]["code"] == "FORBIDDEN"

        # EMPLOYEE role CAN list -> 200
        res_list_emp = await client.get("/employees", headers=emp_headers)
        assert res_list_emp.status_code == 200


@pytest.mark.asyncio
async def test_create_employee_success_and_fields(setup_db_and_app):
    hr_headers = make_auth_headers(role="HR")
    payload = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "department": "Engineering",
        "designation": "Senior Engineer",
        "role": "EMPLOYEE",
        "initial_password": "InitialPassword123!",
        "monthly_salary": 7500.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/employees", json=payload, headers=hr_headers)
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert data["name"] == "John Doe"
        assert data["email"] == "john.doe@example.com"
        assert data["department"] == "Engineering"
        assert data["designation"] == "Senior Engineer"
        assert data["status"] == "PENDING_ONBOARDING"
        assert data["manager_id"] is None
        # Verify saga inputs are NOT in response
        assert "initial_password" not in data
        assert "monthly_salary" not in data
        assert "password" not in data


@pytest.mark.asyncio
async def test_create_employee_duplicate_email(setup_db_and_app):
    hr_headers = make_auth_headers(role="HR")
    dup_email = "dup.email@example.com"
    payload = {
        "name": "User 1",
        "email": dup_email,
        "department": "HR",
        "designation": "Specialist",
        "initial_password": "Password123!",
        "monthly_salary": 5000.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/employees", json=payload, headers=hr_headers)
        assert res1.status_code == 201

        res2 = await client.post("/employees", json=payload, headers=hr_headers)
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_employee_invalid_manager(setup_db_and_app):
    hr_headers = make_auth_headers(role="HR")
    fake_manager_id = str(uuid4())
    payload = {
        "name": "User Bad Manager",
        "email": "bad.manager@example.com",
        "department": "Support",
        "designation": "Agent",
        "manager_id": fake_manager_id,
        "initial_password": "Password123!",
        "monthly_salary": 4000.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/employees", json=payload, headers=hr_headers)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_employee_by_id_and_not_found(setup_db_and_app):
    admin_headers = make_auth_headers(role="ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        res_create = await client.post(
            "/employees",
            json={
                "name": "Alice Smith",
                "email": "alice.smith@example.com",
                "department": "Finance",
                "designation": "Analyst",
                "initial_password": "Password123!",
                "monthly_salary": 6000.00,
            },
            headers=admin_headers,
        )
        assert res_create.status_code == 201
        emp_id = res_create.json()["id"]

        # Get existing
        res_get = await client.get(f"/employees/{emp_id}", headers=admin_headers)
        assert res_get.status_code == 200
        assert res_get.json()["id"] == emp_id

        # Get missing
        res_missing = await client.get(f"/employees/{uuid4()}", headers=admin_headers)
        assert res_missing.status_code == 404
        assert res_missing.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_employees_pagination_and_filter(setup_db_and_app):
    admin_headers = make_auth_headers(role="ADMIN")
    dept = f"Dept_{uuid4().hex[:6]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create 3 employees in dept
        for i in range(3):
            await client.post(
                "/employees",
                json={
                    "name": f"Dept User {i}",
                    "email": f"dept_{dept}_{i}@example.com",
                    "department": dept,
                    "designation": "Dev",
                    "initial_password": "Password123!",
                    "monthly_salary": 5000.00,
                },
                headers=admin_headers,
            )

        # List with department filter
        res_filter = await client.get(
            f"/employees?department={dept}&page=1&page_size=2", headers=admin_headers
        )
        assert res_filter.status_code == 200
        data = res_filter.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_update_employee_success_and_validations(setup_db_and_app):
    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create manager
        mgr_res = await client.post(
            "/employees",
            json={
                "name": "Manager Bob",
                "email": "mgr.bob@example.com",
                "department": "Ops",
                "designation": "Manager",
                "initial_password": "Password123!",
                "monthly_salary": 8000.00,
            },
            headers=hr_headers,
        )
        mgr_id = mgr_res.json()["id"]

        # Create employee
        emp_res = await client.post(
            "/employees",
            json={
                "name": "Subordinate Charlie",
                "email": "sub.charlie@example.com",
                "department": "Ops",
                "designation": "Staff",
                "initial_password": "Password123!",
                "monthly_salary": 4500.00,
            },
            headers=hr_headers,
        )
        emp_id = emp_res.json()["id"]

        # Update manager_id and designation
        update_res = await client.put(
            f"/employees/{emp_id}",
            json={"designation": "Senior Staff", "manager_id": mgr_id, "status": "ACTIVE"},
            headers=hr_headers,
        )
        assert update_res.status_code == 200
        updated_data = update_res.json()
        assert updated_data["designation"] == "Senior Staff"
        assert updated_data["manager_id"] == mgr_id
        # Status MUST NOT be updated via PUT
        assert updated_data["status"] == "PENDING_ONBOARDING"

        # Update self-manager -> 422
        self_mgr_res = await client.put(
            f"/employees/{emp_id}",
            json={"manager_id": emp_id},
            headers=hr_headers,
        )
        assert self_mgr_res.status_code == 422
        assert self_mgr_res.json()["error"]["code"] == "VALIDATION_ERROR"

        # Update duplicate email -> 409
        dup_email_res = await client.put(
            f"/employees/{emp_id}",
            json={"email": "mgr.bob@example.com"},
            headers=hr_headers,
        )
        assert dup_email_res.status_code == 409
        assert dup_email_res.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_delete_employee_soft_delete_and_idempotency(setup_db_and_app):
    admin_headers = make_auth_headers(role="ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        emp_res = await client.post(
            "/employees",
            json={
                "name": "Delete Me",
                "email": "del.me@example.com",
                "department": "QA",
                "designation": "Tester",
                "initial_password": "Password123!",
                "monthly_salary": 4000.00,
            },
            headers=admin_headers,
        )
        emp_id = emp_res.json()["id"]

        # Delete -> 204
        del1 = await client.delete(f"/employees/{emp_id}", headers=admin_headers)
        assert del1.status_code == 204

        # Repeat Delete -> 204 (idempotent soft delete)
        del2 = await client.delete(f"/employees/{emp_id}", headers=admin_headers)
        assert del2.status_code == 204

        # GET by ID -> 404
        get_res = await client.get(f"/employees/{emp_id}", headers=admin_headers)
        assert get_res.status_code == 404

        # Non-existent ID delete -> 404
        fake_id = str(uuid4())
        del_fake = await client.delete(f"/employees/{fake_id}", headers=admin_headers)
        assert del_fake.status_code == 404
