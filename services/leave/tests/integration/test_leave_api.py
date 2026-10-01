import json
import os
from datetime import date, datetime, timedelta, timezone
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

try:
    from testcontainers.redis import RedisContainer
except ImportError:
    from testcontainers.community.redis import RedisContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

import jwt
from ems_common.config import settings as common_settings
from ems_common.errors import EMSError
from ems_common.http_client import ResilientHTTPClient, create_circuit_breaker
from services.leave.app.api.routes import get_db
from services.leave.app.clients.employee_client import EmployeeClient
from services.leave.app.config import settings
from services.leave.app.main import app
from services.leave.app.models.leave import Base, Leave, OutboxBase, OutboxMessage

# Disable background outbox publisher in test suite
settings.OUTBOX_PUBLISHER_ENABLED = False


@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest_asyncio.fixture(scope="module")
async def setup_db_and_app(postgres_container, redis_container):
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )

    settings.DATABASE_URL = async_url
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)
    settings.REDIS_URL = f"redis://{redis_host}:{redis_port}/0"

    engine = create_async_engine(async_url, poolclass=NullPool, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(OutboxBase.metadata.create_all)

    async def get_test_db():
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = get_test_db

    yield async_session_factory

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_app_state(setup_db_and_app):
    # Initialize fresh EmployeeClient for each test
    app.state.employee_client = EmployeeClient(
        employee_service_url=settings.EMPLOYEE_SERVICE_URL,
        redis_url=settings.REDIS_URL,
    )


def make_auth_headers(role: str = "EMPLOYEE", user_id: str = None) -> dict:
    uid = user_id or str(uuid4())
    payload = {
        "sub": uid,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, common_settings.JWT_SECRET, algorithm=common_settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_and_metrics(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_h = await client.get("/health")
        assert res_h.status_code == 200
        assert res_h.json() == {"status": "ok"}

        res_m = await client.get("/metrics")
        assert res_m.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_and_invalid_token(setup_db_and_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_no_token = await client.get("/leaves")
        assert res_no_token.status_code == 401

        res_bad_token = await client.get(
            "/leaves", headers={"Authorization": "Bearer invalid_jwt_token"}
        )
        assert res_bad_token.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_success_and_outbox_event(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    mgr_id = str(uuid4())

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200,
            json={"id": emp_id, "status": "ACTIVE", "manager_id": mgr_id},
        )
    )

    corr_id = f"corr-leave-{uuid4().hex[:6]}"
    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    headers["X-Correlation-ID"] = corr_id

    payload = {
        "employee_id": emp_id,
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "leave_type": "PAID",
        "reason": "Vacation",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/leaves", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        leave_id = data["id"]
        assert data["employee_id"] == emp_id
        assert data["manager_id"] == mgr_id
        assert data["days"] == 5
        assert data["status"] == "PENDING"

        # Verify Outbox row
        async with session_factory() as session:
            stmt = select(OutboxMessage).where(OutboxMessage.payload.like(f"%{leave_id}%"))
            outbox_res = await session.execute(stmt)
            msgs = list(outbox_res.scalars().all())
            assert len(msgs) == 1
            msg = msgs[0]
            assert msg.event_type == "LeaveRequested"
            assert msg.correlation_id == corr_id
            msg_payload = json.loads(msg.payload)
            assert msg_payload["leave_id"] == leave_id
            assert msg_payload["employee_id"] == emp_id
            assert msg_payload["days"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_employee_not_found_422(setup_db_and_app):
    emp_id = str(uuid4())
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )

    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    payload = {
        "employee_id": emp_id,
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "leave_type": "PAID",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/leaves", json=payload, headers=headers)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "INVALID_EMPLOYEE"


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_employee_not_active_422(setup_db_and_app):
    emp_id = str(uuid4())
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ONBOARDING_FAILED", "manager_id": None}
        )
    )

    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    payload = {
        "employee_id": emp_id,
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "leave_type": "PAID",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/leaves", json=payload, headers=headers)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "INVALID_EMPLOYEE"


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_employee_service_down_503(setup_db_and_app):
    emp_id = str(uuid4())
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(500, json={"error": "down"})
    )

    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    payload = {
        "employee_id": emp_id,
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "leave_type": "PAID",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/leaves", json=payload, headers=headers)
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "EMPLOYEE_SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_cache_hit_and_auth_header_forwarded(setup_db_and_app):
    emp_id = str(uuid4())
    emp_route = respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1st call -> hits Employee service
        res1 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-07-01",
                "end_date": "2026-07-03",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res1.status_code == 201
        assert emp_route.call_count == 1
        assert emp_route.calls.last.request.headers.get("authorization") == headers["Authorization"]

        # 2nd call -> served from Redis cache!
        res2 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-07-10",
                "end_date": "2026-07-14",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res2.status_code == 201
        assert emp_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_redis_unreachable_fallback(setup_db_and_app):
    emp_id = str(uuid4())
    emp_route = respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    app.state.employee_client = EmployeeClient(
        employee_service_url=settings.EMPLOYEE_SERVICE_URL,
        redis_url="redis://invalid-host:6379/0",
    )

    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-08-03",
                "end_date": "2026-08-05",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res.status_code == 201
        assert emp_route.call_count == 1


@pytest.mark.asyncio
async def test_create_leave_forbidden_for_other_employee(setup_db_and_app):
    emp_id = str(uuid4())
    other_id = str(uuid4())
    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/leaves",
            json={
                "employee_id": other_id,
                "start_date": "2026-06-01",
                "end_date": "2026-06-05",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_overlap_409(setup_db_and_app):
    emp_id = str(uuid4())
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )
    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-09-01",
                "end_date": "2026-09-07",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res1.status_code == 201
        # Approve leave so overlap is tested against an APPROVED leave
        await client.post(f"/leaves/{res1.json()['id']}/approve", headers=hr_headers)

        res2 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-09-04",
                "end_date": "2026-09-10",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res2.status_code == 409
        assert res2.json()["error"]["code"] == "LEAVE_OVERLAP"


@pytest.mark.asyncio
@respx.mock
async def test_create_leave_paid_over_balance_422_and_unpaid_allowed(setup_db_and_app):
    emp_id = str(uuid4())
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )
    headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create PAID leave for 15 days (June 1 to June 19)
        res1 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-06-01",
                "end_date": "2026-06-19",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res1.status_code == 201

        # Approve leave so it counts as used
        hr_headers = make_auth_headers(role="HR")
        await client.post(f"/leaves/{res1.json()['id']}/approve", headers=hr_headers)

        # Attempt 10 more PAID days (15 + 10 = 25 > 20) -> 422
        res2 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-07-01",
                "end_date": "2026-07-14",
                "leave_type": "PAID",
            },
            headers=headers,
        )
        assert res2.status_code == 422
        assert res2.json()["error"]["code"] == "INSUFFICIENT_LEAVE_BALANCE"

        # UNPAID leave for 10 days -> 201 (unpaid skips balance check!)
        res3 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-07-01",
                "end_date": "2026-07-14",
                "leave_type": "UNPAID",
            },
            headers=headers,
        )
        assert res3.status_code == 201


@pytest.mark.asyncio
@respx.mock
async def test_approve_leave_by_own_manager_works(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    mgr_id = str(uuid4())

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": mgr_id}
        )
    )

    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    mgr_headers = make_auth_headers(role="MANAGER", user_id=mgr_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-10-05",
                "end_date": "2026-10-09",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        leave_id = create_res.json()["id"]

        res_ok = await client.post(f"/leaves/{leave_id}/approve", headers=mgr_headers)
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "APPROVED"
        assert res_ok.json()["decided_by"] == mgr_id


@pytest.mark.asyncio
@respx.mock
async def test_approve_leave_permissions_and_forbidden(setup_db_and_app):
    emp_id = str(uuid4())
    mgr_id = str(uuid4())
    other_mgr_id = str(uuid4())

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": mgr_id}
        )
    )

    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    other_mgr_headers = make_auth_headers(role="MANAGER", user_id=other_mgr_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-10-12",
                "end_date": "2026-10-16",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        leave_id = create_res.json()["id"]

        # Different MANAGER approves -> 403
        res_other = await client.post(f"/leaves/{leave_id}/approve", headers=other_mgr_headers)
        assert res_other.status_code == 403

        # Self approve (if manager role for own leave) -> 403
        emp_as_mgr_headers = make_auth_headers(role="MANAGER", user_id=emp_id)
        res_self = await client.post(f"/leaves/{leave_id}/approve", headers=emp_as_mgr_headers)
        assert res_self.status_code == 403

        # EMPLOYEE approves -> 403
        res_emp_app = await client.post(f"/leaves/{leave_id}/approve", headers=emp_headers)
        assert res_emp_app.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_approve_leave_by_hr_works(setup_db_and_app):
    emp_id = str(uuid4())
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )
    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-11-16",
                "end_date": "2026-11-20",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        leave_id = create_res.json()["id"]

        res_hr = await client.post(f"/leaves/{leave_id}/approve", headers=hr_headers)
        assert res_hr.status_code == 200
        assert res_hr.json()["status"] == "APPROVED"


@pytest.mark.asyncio
@respx.mock
async def test_second_approve_returns_409_and_single_outbox_row(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    hr_headers = make_auth_headers(role="HR")

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-10-19",
                "end_date": "2026-10-23",
                "leave_type": "PAID",
            },
            headers=hr_headers,
        )
        leave_id = create_res.json()["id"]

        # First approve -> 200
        res_ok = await client.post(f"/leaves/{leave_id}/approve", headers=hr_headers)
        assert res_ok.status_code == 200

        # Second approve -> 409
        res_dup = await client.post(f"/leaves/{leave_id}/approve", headers=hr_headers)
        assert res_dup.status_code == 409

        # Verify exactly ONE LeaveApproved outbox row
        async with session_factory() as session:
            stmt = select(OutboxMessage).where(
                OutboxMessage.event_type == "LeaveApproved",
                OutboxMessage.payload.like(f"%{leave_id}%"),
            )
            outbox_res = await session.execute(stmt)
            msgs = list(outbox_res.scalars().all())
            assert len(msgs) == 1


@pytest.mark.asyncio
@respx.mock
async def test_reject_leave_writes_outbox(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    hr_headers = make_auth_headers(role="HR")

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-11-02",
                "end_date": "2026-11-06",
                "leave_type": "PAID",
            },
            headers=hr_headers,
        )
        leave_id = create_res.json()["id"]

        # HR rejects -> 200
        res_rej = await client.post(f"/leaves/{leave_id}/reject", headers=hr_headers)
        assert res_rej.status_code == 200
        assert res_rej.json()["status"] == "REJECTED"

        # Verify LeaveRejected outbox event
        async with session_factory() as session:
            stmt = select(OutboxMessage).where(
                OutboxMessage.event_type == "LeaveRejected",
                OutboxMessage.payload.like(f"%{leave_id}%"),
            )
            outbox_res = await session.execute(stmt)
            assert len(list(outbox_res.scalars().all())) == 1


@pytest.mark.asyncio
@respx.mock
async def test_cancel_pending_leave_no_event(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-12-01",
                "end_date": "2026-12-04",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        l1_id = res1.json()["id"]

        cancel1 = await client.post(f"/leaves/{l1_id}/cancel", headers=emp_headers)
        assert cancel1.status_code == 200
        assert cancel1.json()["status"] == "CANCELLED"

        async with session_factory() as session:
            stmt = select(OutboxMessage).where(OutboxMessage.payload.like(f"%{l1_id}%"))
            res_out1 = await session.execute(stmt)
            events = [msg.event_type for msg in res_out1.scalars().all()]
            assert "LeaveCancelled" not in events


@pytest.mark.asyncio
@respx.mock
async def test_cancel_approved_leave_writes_event(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    hr_headers = make_auth_headers(role="HR")

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-12-14",
                "end_date": "2026-12-18",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        l2_id = res2.json()["id"]
        await client.post(f"/leaves/{l2_id}/approve", headers=hr_headers)

        cancel2 = await client.post(f"/leaves/{l2_id}/cancel", headers=emp_headers)
        assert cancel2.status_code == 200
        assert cancel2.json()["status"] == "CANCELLED"

        async with session_factory() as session:
            stmt = select(OutboxMessage).where(
                OutboxMessage.event_type == "LeaveCancelled",
                OutboxMessage.payload.like(f"%{l2_id}%"),
            )
            res_out2 = await session.execute(stmt)
            assert len(list(res_out2.scalars().all())) == 1


@pytest.mark.asyncio
@respx.mock
async def test_cancel_rejected_leave_returns_409(setup_db_and_app):
    emp_id = str(uuid4())
    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    hr_headers = make_auth_headers(role="HR")

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res3 = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-12-21",
                "end_date": "2026-12-25",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        l3_id = res3.json()["id"]
        await client.post(f"/leaves/{l3_id}/reject", headers=hr_headers)

        cancel3 = await client.post(f"/leaves/{l3_id}/cancel", headers=emp_headers)
        assert cancel3.status_code == 409


@pytest.mark.asyncio
@respx.mock
async def test_balance_endpoint_and_access_control(setup_db_and_app):
    emp_id = str(uuid4())
    other_id = str(uuid4())

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    emp_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id)
    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create and approve 5 paid days (APPROVED PAID -> counts as 5 used)
        res_approved_paid = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-05-04",
                "end_date": "2026-05-08",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )
        await client.post(f"/leaves/{res_approved_paid.json()['id']}/approve", headers=hr_headers)

        # 2. Create PENDING paid leave (PENDING PAID -> should NOT count in used balance)
        await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-05-18",
                "end_date": "2026-05-22",
                "leave_type": "PAID",
            },
            headers=emp_headers,
        )

        # 3. Create and approve UNPAID leave (APPROVED UNPAID -> should NOT count in used balance)
        res_approved_unpaid = await client.post(
            "/leaves",
            json={
                "employee_id": emp_id,
                "start_date": "2026-06-01",
                "end_date": "2026-06-05",
                "leave_type": "UNPAID",
            },
            headers=emp_headers,
        )
        await client.post(f"/leaves/{res_approved_unpaid.json()['id']}/approve", headers=hr_headers)

        # Self query balance -> 200 (used balance counts ONLY approved paid leaves: 5 days)
        res_self = await client.get(
            f"/leaves/balance/{emp_id}?year=2026", headers=emp_headers
        )
        assert res_self.status_code == 200
        bal = res_self.json()
        assert bal["allowance"] == 20
        assert bal["used"] == 5
        assert bal["remaining"] == 15

        # Query other employee balance as EMPLOYEE -> 403
        res_other = await client.get(
            f"/leaves/balance/{other_id}?year=2026", headers=emp_headers
        )
        assert res_other.status_code == 403

        # Query other employee balance as HR -> 200
        res_hr = await client.get(
            f"/leaves/balance/{other_id}?year=2026", headers=hr_headers
        )
        assert res_hr.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_list_leaves_visibility(setup_db_and_app):
    emp1_id = str(uuid4())
    emp2_id = str(uuid4())
    mgr_id = str(uuid4())

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp1_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp1_id, "status": "ACTIVE", "manager_id": mgr_id}
        )
    )
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/{emp2_id}").mock(
        return_value=httpx.Response(
            200, json={"id": emp2_id, "status": "ACTIVE", "manager_id": None}
        )
    )

    emp1_headers = make_auth_headers(role="EMPLOYEE", user_id=emp1_id)
    emp2_headers = make_auth_headers(role="EMPLOYEE", user_id=emp2_id)
    mgr_headers = make_auth_headers(role="MANAGER", user_id=mgr_id)
    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create leave for emp1 (managed by mgr)
        await client.post(
            "/leaves",
            json={
                "employee_id": emp1_id,
                "start_date": "2026-08-10",
                "end_date": "2026-08-14",
                "leave_type": "PAID",
            },
            headers=emp1_headers,
        )

        # Create leave for emp2 (no manager)
        await client.post(
            "/leaves",
            json={
                "employee_id": emp2_id,
                "start_date": "2026-08-17",
                "end_date": "2026-08-21",
                "leave_type": "PAID",
            },
            headers=emp2_headers,
        )

        # EMPLOYEE 1 lists -> sees only emp1's leave
        res_e1 = await client.get("/leaves", headers=emp1_headers)
        assert res_e1.status_code == 200
        assert res_e1.json()["total"] == 1
        assert res_e1.json()["items"][0]["employee_id"] == emp1_id

        # MANAGER lists -> sees emp1's leave
        res_m = await client.get("/leaves", headers=mgr_headers)
        assert res_m.status_code == 200
        assert res_m.json()["total"] == 1
        assert res_m.json()["items"][0]["employee_id"] == emp1_id

        # HR lists -> sees both leaves
        res_hr = await client.get("/leaves", headers=hr_headers)
        assert res_hr.status_code == 200
        returned_emp_ids = {item["employee_id"] for item in res_hr.json()["items"]}
        assert emp1_id in returned_emp_ids
        assert emp2_id in returned_emp_ids
