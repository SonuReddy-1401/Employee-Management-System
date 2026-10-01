import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
import httpx
import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:
    from testcontainers.community.postgres import PostgresContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

import jwt
from ems_common.errors import EMSError
from ems_common.http_client import ResilientHTTPClient, create_circuit_breaker
from services.employee.app.api.routes import get_db
from services.employee.app.config import settings
from services.employee.app.domain.saga import OnboardingSaga
from services.employee.app.main import app
from services.employee.app.models.employee import Base, Employee, OutboxMessage
from services.employee.app.schemas.employee import EmployeeCreateRequest

# Disable background outbox publisher in test suite
settings.OUTBOX_PUBLISHER_ENABLED = False


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

    yield async_session_factory

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
@respx.mock
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
@respx.mock
async def test_create_employee_success_and_fields(setup_db_and_app):
    session_factory = setup_db_and_app

    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

    hr_headers = make_auth_headers(role="HR")
    payload = {
        "name": "John Doe",
        "email": f"john.doe_{uuid4().hex[:4]}@example.com",
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
        assert data["department"] == "Engineering"
        assert data["designation"] == "Senior Engineer"
        assert data["status"] == "ACTIVE"
        assert data["manager_id"] is None
        # Verify saga inputs are NOT in response
        assert "initial_password" not in data
        assert "monthly_salary" not in data

        # Verify outbox row created
        emp_id = data["id"]
        async with session_factory() as session:
            stmt = select(OutboxMessage).where(OutboxMessage.payload.like(f"%{emp_id}%"))
            outbox_res = await session.execute(stmt)
            outbox_msgs = list(outbox_res.scalars().all())
            assert len(outbox_msgs) == 1
            assert outbox_msgs[0].event_type == "EmployeeOnboarded"


@pytest.mark.asyncio
@respx.mock
async def test_create_employee_duplicate_email(setup_db_and_app):
    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

    hr_headers = make_auth_headers(role="HR")
    dup_email = f"dup.email_{uuid4().hex[:4]}@example.com"
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
@respx.mock
async def test_create_employee_invalid_manager(setup_db_and_app):
    auth_route = respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    payroll_route = respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

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
        assert not auth_route.called
        assert not payroll_route.called


@pytest.mark.asyncio
@respx.mock
async def test_saga_payroll_500_failure_and_compensation(setup_db_and_app):
    session_factory = setup_db_and_app

    auth_route = respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    payroll_route = respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(500, json={"error": "db error"})
    )
    auth_comp_route = respx.delete(f"{settings.AUTH_SERVICE_URL}/internal/users/").mock(
        return_value=httpx.Response(204)
    )

    hr_headers = make_auth_headers(role="HR")
    email = f"payroll.fail_{uuid4().hex[:4]}@example.com"
    payload = {
        "name": "Payroll Fail User",
        "email": email,
        "department": "Dev",
        "designation": "Engineer",
        "initial_password": "Password123!",
        "monthly_salary": 6000.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/employees", json=payload, headers=hr_headers)
        assert res.status_code == 502
        assert res.json()["error"]["code"] == "ONBOARDING_FAILED"

        # Check DB status is ONBOARDING_FAILED and NO outbox row
        async with session_factory() as session:
            stmt = select(Employee).where(Employee.email == email)
            emp_res = await session.execute(stmt)
            emp = emp_res.scalar_one()
            assert emp.status == "ONBOARDING_FAILED"

            outbox_stmt = select(OutboxMessage).where(OutboxMessage.payload.like(f"%{emp.id}%"))
            outbox_res = await session.execute(outbox_stmt)
            assert len(list(outbox_res.scalars().all())) == 0

        # Verify GET /employees/{id} returns 200 with status ONBOARDING_FAILED
        res_get = await client.get(f"/employees/{emp.id}", headers=hr_headers)
        assert res_get.status_code == 200
        assert res_get.json()["status"] == "ONBOARDING_FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_saga_auth_500_failure_no_compensation(setup_db_and_app):
    session_factory = setup_db_and_app

    auth_route = respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(500, json={"error": "auth down"})
    )
    payroll_route = respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    auth_comp_route = respx.delete(f"{settings.AUTH_SERVICE_URL}/internal/users/").mock(
        return_value=httpx.Response(204)
    )

    hr_headers = make_auth_headers(role="HR")
    email = f"auth.fail_{uuid4().hex[:4]}@example.com"
    payload = {
        "name": "Auth Fail User",
        "email": email,
        "department": "Dev",
        "designation": "Engineer",
        "initial_password": "Password123!",
        "monthly_salary": 6000.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/employees", json=payload, headers=hr_headers)
        assert res.status_code == 502
        assert res.json()["error"]["code"] == "ONBOARDING_FAILED"

        assert not payroll_route.called
        assert not auth_comp_route.called

        async with session_factory() as session:
            stmt = select(Employee).where(Employee.email == email)
            emp_res = await session.execute(stmt)
            emp = emp_res.scalar_one()
            assert emp.status == "ONBOARDING_FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_saga_payroll_fails_and_auth_compensation_fails(setup_db_and_app):
    session_factory = setup_db_and_app

    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(500, json={"error": "payroll fail"})
    )
    respx.delete(f"{settings.AUTH_SERVICE_URL}/internal/users/").mock(
        return_value=httpx.Response(500, json={"error": "comp fail"})
    )

    hr_headers = make_auth_headers(role="HR")
    email = f"comp.fail_{uuid4().hex[:4]}@example.com"
    payload = {
        "name": "Comp Fail User",
        "email": email,
        "department": "Dev",
        "designation": "Engineer",
        "initial_password": "Password123!",
        "monthly_salary": 6000.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/employees", json=payload, headers=hr_headers)
        assert res.status_code == 502
        assert res.json()["error"]["code"] == "ONBOARDING_FAILED"

        async with session_factory() as session:
            stmt = select(Employee).where(Employee.email == email)
            emp_res = await session.execute(stmt)
            emp = emp_res.scalar_one()
            assert emp.status == "ONBOARDING_FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_saga_circuit_breaker_fast_failure(setup_db_and_app):
    session_factory = setup_db_and_app

    # Create a custom breaker with fail_max=2 for fast test
    custom_breaker = create_circuit_breaker(fail_max=2, reset_timeout=30.0)
    client = ResilientHTTPClient(breaker=custom_breaker)

    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    payroll_route = respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(500, json={"error": "fail"})
    )

    async with session_factory() as session:
        saga = OnboardingSaga(session, http_client=client)

        # 1st failure
        with pytest.raises(EMSError) as exc1:
            await saga.execute(
                EmployeeCreateRequest(
                    name="Fail 1",
                    email=f"fail1_{uuid4().hex[:4]}@example.com",
                    department="Dev",
                    designation="Eng",
                    initial_password="Password123!",
                    monthly_salary=Decimal("5000.00"),
                )
            )
        assert exc1.value.status_code == 502

        # 2nd failure -> trips circuit breaker
        with pytest.raises(EMSError) as exc2:
            await saga.execute(
                EmployeeCreateRequest(
                    name="Fail 2",
                    email=f"fail2_{uuid4().hex[:4]}@example.com",
                    department="Dev",
                    designation="Eng",
                    initial_password="Password123!",
                    monthly_salary=Decimal("5000.00"),
                )
            )
        assert exc2.value.status_code == 502

        # 3rd attempt: Breaker is OPEN -> fails fast with 502 without calling payroll route again
        calls_before = payroll_route.call_count
        with pytest.raises(EMSError) as exc3:
            await saga.execute(
                EmployeeCreateRequest(
                    name="Fail 3",
                    email=f"fail3_{uuid4().hex[:4]}@example.com",
                    department="Dev",
                    designation="Eng",
                    initial_password="Password123!",
                    monthly_salary=Decimal("5000.00"),
                )
            )
        assert exc3.value.status_code == 502
        assert payroll_route.call_count == calls_before

    custom_breaker.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_employee_by_id_and_not_found(setup_db_and_app):
    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

    admin_headers = make_auth_headers(role="ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        res_create = await client.post(
            "/employees",
            json={
                "name": "Alice Smith",
                "email": f"alice.smith_{uuid4().hex[:4]}@example.com",
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
@respx.mock
async def test_list_employees_pagination_and_filter(setup_db_and_app):
    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

    admin_headers = make_auth_headers(role="ADMIN")
    dept = f"Dept_{uuid4().hex[:6]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

        res_filter = await client.get(
            f"/employees?department={dept}&page=1&page_size=2", headers=admin_headers
        )
        assert res_filter.status_code == 200
        data = res_filter.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_update_employee_success_and_validations(setup_db_and_app):
    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create manager
        mgr_res = await client.post(
            "/employees",
            json={
                "name": "Manager Bob",
                "email": f"mgr.bob_{uuid4().hex[:4]}@example.com",
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
                "email": f"sub.charlie_{uuid4().hex[:4]}@example.com",
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
            json={"designation": "Senior Staff", "manager_id": mgr_id},
            headers=hr_headers,
        )
        assert update_res.status_code == 200
        updated_data = update_res.json()
        assert updated_data["designation"] == "Senior Staff"
        assert updated_data["manager_id"] == mgr_id

        # Update self-manager -> 422
        self_mgr_res = await client.put(
            f"/employees/{emp_id}",
            json={"manager_id": emp_id},
            headers=hr_headers,
        )
        assert self_mgr_res.status_code == 422


@pytest.mark.asyncio
@respx.mock
async def test_delete_employee_soft_delete_and_idempotency(setup_db_and_app):
    respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )
    respx.post(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles").mock(
        return_value=httpx.Response(201, json={"status": "ok"})
    )

    admin_headers = make_auth_headers(role="ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        emp_res = await client.post(
            "/employees",
            json={
                "name": "Delete Me",
                "email": f"del.me_{uuid4().hex[:4]}@example.com",
                "department": "QA",
                "designation": "Tester",
                "initial_password": "Password123!",
                "monthly_salary": 4000.00,
            },
            headers=admin_headers,
        )
        emp_id = emp_res.json()["id"]

        del1 = await client.delete(f"/employees/{emp_id}", headers=admin_headers)
        assert del1.status_code == 204

        del2 = await client.delete(f"/employees/{emp_id}", headers=admin_headers)
        assert del2.status_code == 204

        get_res = await client.get(f"/employees/{emp_id}", headers=admin_headers)
        assert get_res.status_code == 404
