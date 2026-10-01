import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:
    from testcontainers.community.postgres import PostgresContainer

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from ems_common.events import EventEnvelope, EventType
from services.payroll.app.api.routes import get_db
from services.payroll.app.config import settings
from services.payroll.app.domain.payroll import handle_leave_approved
from services.payroll.app.main import app
from services.payroll.app.models.payroll import Base, LeaveDeduction


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
async def test_profile_crud_and_idempotency(setup_db_and_app):
    emp_id = str(uuid4())
    salary = 6000.00

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create 201
        res1 = await client.post(
            "/internal/profiles", json={"employee_id": emp_id, "monthly_salary": salary}
        )
        assert res1.status_code == 201
        assert res1.json()["employee_id"] == emp_id
        assert Decimal(str(res1.json()["monthly_salary"])) == Decimal("6000.00")

        # Same create 200 (idempotent with same salary)
        res2 = await client.post(
            "/internal/profiles", json={"employee_id": emp_id, "monthly_salary": salary}
        )
        assert res2.status_code == 200
        assert res2.json()["employee_id"] == emp_id

        # Different salary -> 409 CONFLICT
        res_diff = await client.post(
            "/internal/profiles", json={"employee_id": emp_id, "monthly_salary": 7000.00}
        )
        assert res_diff.status_code == 409
        assert res_diff.json()["error"]["code"] == "CONFLICT"

        # Invalid salary (<= 0) -> 422
        res_invalid = await client.post(
            "/internal/profiles", json={"employee_id": str(uuid4()), "monthly_salary": -100.00}
        )
        assert res_invalid.status_code == 422

        # Delete 204
        del1 = await client.delete(f"/internal/profiles/{emp_id}")
        assert del1.status_code == 204

        # Repeat Delete 204
        del2 = await client.delete(f"/internal/profiles/{emp_id}")
        assert del2.status_code == 204


@pytest.mark.asyncio
async def test_payroll_run_calculation_and_idempotency(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    salary = 5000.00  # 5000.00 in March 2024 (21 weekdays)

    # Insert UNPAID leave deduction via event handler
    event_id = uuid4()
    leave_id = uuid4()
    event_envelope = EventEnvelope(
        event_id=event_id,
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": emp_id,
            "start_date": "2024-03-11",  # Mon
            "end_date": "2024-03-13",    # Wed (3 days)
            "leave_type": "UNPAID",
            "days": 3,
        },
    )

    async with session_factory() as session:
        await handle_leave_approved(session, event_envelope)

    hr_headers = make_auth_headers(role="HR")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create profile
        await client.post("/internal/profiles", json={"employee_id": emp_id, "monthly_salary": salary})

        # Bad month 422
        res_bad_month = await client.post("/payroll/run?month=bad-month", headers=hr_headers)
        assert res_bad_month.status_code == 422

        # EMPLOYEE role forbidden 403
        emp_headers = make_auth_headers(role="EMPLOYEE")
        res_emp_run = await client.post("/payroll/run?month=2024-03", headers=emp_headers)
        assert res_emp_run.status_code == 403

        # Run payroll 200
        res_run1 = await client.post("/payroll/run?month=2024-03", headers=hr_headers)
        assert res_run1.status_code == 200
        data1 = res_run1.json()
        assert data1["month"] == "2024-03"
        assert data1["created"] >= 1

        # Run payroll second time -> created 0, skipped >= 1
        res_run2 = await client.post("/payroll/run?month=2024-03", headers=hr_headers)
        assert res_run2.status_code == 200
        data2 = res_run2.json()
        assert data2["created"] == 0
        assert data2["skipped"] >= 1

        # Check calculated payslip numbers
        # March 2024: 21 weekdays. 3 unpaid days. 5000 / 21 * 3 = 714.2857... -> 714.29 deduction, net 4285.71
        res_payslips = await client.get(f"/payslips/{emp_id}", headers=hr_headers)
        assert res_payslips.status_code == 200
        payslip_list = res_payslips.json()
        assert len(payslip_list) == 1
        ps = payslip_list[0]
        assert ps["employee_id"] == emp_id
        assert ps["month"] == "2024-03"
        assert Decimal(str(ps["gross_salary"])) == Decimal("5000.00")
        assert ps["unpaid_leave_days"] == 3
        assert Decimal(str(ps["deduction"])) == Decimal("714.29")
        assert Decimal(str(ps["net_salary"])) == Decimal("4285.71")


@pytest.mark.asyncio
async def test_payslip_access_control(setup_db_and_app):
    emp_id_1 = str(uuid4())
    emp_id_2 = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create profile for emp 1
        await client.post("/internal/profiles", json={"employee_id": emp_id_1, "monthly_salary": 4000.00})

        # Run payroll
        hr_headers = make_auth_headers(role="HR")
        await client.post("/payroll/run?month=2024-04", headers=hr_headers)

        # EMPLOYEE 1 reading own payslips -> 200
        emp1_headers = make_auth_headers(role="EMPLOYEE", user_id=emp_id_1)
        res_own = await client.get(f"/payslips/{emp_id_1}", headers=emp1_headers)
        assert res_own.status_code == 200

        # EMPLOYEE 1 reading EMPLOYEE 2 payslips -> 403 FORBIDDEN
        res_other = await client.get(f"/payslips/{emp_id_2}", headers=emp1_headers)
        assert res_other.status_code == 403
        assert res_other.json()["error"]["code"] == "FORBIDDEN"

        # HR reading EMPLOYEE 1 payslips -> 200
        res_hr = await client.get(f"/payslips/{emp_id_1}", headers=hr_headers)
        assert res_hr.status_code == 200


@pytest.mark.asyncio
async def test_handle_leave_approved_idempotency_and_paid_leave(setup_db_and_app):
    session_factory = setup_db_and_app
    emp_id = uuid4()
    event_id = uuid4()
    leave_id = uuid4()

    unpaid_event = EventEnvelope(
        event_id=event_id,
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-05-06",
            "end_date": "2024-05-10",
            "leave_type": "UNPAID",
            "days": 5,
        },
    )

    # Process first time
    async with session_factory() as session:
        await handle_leave_approved(session, unpaid_event)

    # Process second time with SAME event_id
    async with session_factory() as session:
        await handle_leave_approved(session, unpaid_event)

    # Verify exactly ONE row in leave_deductions for this leave_id
    async with session_factory() as session:
        stmt = select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id)
        res = await session.execute(stmt)
        rows = list(res.scalars().all())
        assert len(rows) == 1

    # Process PAID leave event
    paid_leave_id = uuid4()
    paid_event = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(paid_leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-05-13",
            "end_date": "2024-05-17",
            "leave_type": "PAID",
            "days": 5,
        },
    )

    async with session_factory() as session:
        await handle_leave_approved(session, paid_event)

    # Verify NO row created for PAID leave
    async with session_factory() as session:
        stmt = select(LeaveDeduction).where(LeaveDeduction.leave_id == paid_leave_id)
        res = await session.execute(stmt)
        rows = list(res.scalars().all())
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_handle_leave_cancelled_and_out_of_order(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    from services.payroll.app.models.payroll import CancelledLeave

    session_factory = setup_db_and_app
    emp_id = uuid4()
    leave_id = uuid4()

    unpaid_approved_event = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-06-03",
            "end_date": "2024-06-07",
            "leave_type": "UNPAID",
            "days": 5,
        },
    )

    cancelled_event = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_CANCELLED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-06-03",
            "end_date": "2024-06-07",
            "leave_type": "UNPAID",
            "days": 5,
        },
    )

    # 1. Approve leave -> deduction created
    async with session_factory() as session:
        await handle_payroll_event(session, unpaid_approved_event)
        await session.commit()

    async with session_factory() as session:
        res = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
        assert res.scalar_one_or_none() is not None

    # 2. Cancel leave -> deduction deleted & recorded in CancelledLeave
    async with session_factory() as session:
        await handle_payroll_event(session, cancelled_event)
        await session.commit()

    async with session_factory() as session:
        res1 = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
        assert res1.scalar_one_or_none() is None
        res2 = await session.execute(select(CancelledLeave).where(CancelledLeave.leave_id == leave_id))
        assert res2.scalar_one_or_none() is not None

    # 3. Out-of-order late LeaveApproved arrives AFTER LeaveCancelled -> ignored (no deduction re-added)
    async with session_factory() as session:
        await handle_payroll_event(session, unpaid_approved_event)
        await session.commit()

    async with session_factory() as session:
        res3 = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
        assert res3.scalar_one_or_none() is None
