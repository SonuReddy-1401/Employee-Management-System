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

    from ems_common.consumer import ConsumerBase

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ConsumerBase.metadata.create_all)

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


@pytest.mark.asyncio
async def test_p1_leave_approved_then_cancelled_payslip_zero_unpaid(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    emp_id = str(uuid4())
    leave_id = uuid4()
    salary = 5000.00

    # 1. Create profile
    hr_headers = make_auth_headers(role="HR")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/internal/profiles", json={"employee_id": emp_id, "monthly_salary": salary})

    # 2. LeaveApproved UNPAID
    approved_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": emp_id,
            "start_date": "2024-03-11",
            "end_date": "2024-03-13",
            "leave_type": "UNPAID",
            "days": 3,
        },
    )
    async with session_factory() as session:
        await handle_payroll_event(session, approved_evt)
        await session.commit()

    # 3. LeaveCancelled
    cancelled_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_CANCELLED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": emp_id,
            "start_date": "2024-03-11",
            "end_date": "2024-03-13",
            "leave_type": "UNPAID",
            "days": 3,
        },
    )
    async with session_factory() as session:
        await handle_payroll_event(session, cancelled_evt)
        await session.commit()

    # 4. Verify deduction removed and payslip has 0 unpaid days
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/payroll/run?month=2024-03", headers=hr_headers)
        res = await client.get(f"/payslips/{emp_id}", headers=hr_headers)
        assert res.status_code == 200
        payslip = res.json()[0]
        assert payslip["unpaid_leave_days"] == 0
        assert Decimal(str(payslip["deduction"])) == Decimal("0.00")
        assert Decimal(str(payslip["net_salary"])) == Decimal("5000.00")


@pytest.mark.asyncio
async def test_p2_leave_cancelled_before_leave_approved(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    emp_id = uuid4()
    leave_id = uuid4()

    cancelled_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_CANCELLED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-07-01",
            "end_date": "2024-07-05",
            "leave_type": "UNPAID",
            "days": 5,
        },
    )
    approved_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-07-01",
            "end_date": "2024-07-05",
            "leave_type": "UNPAID",
            "days": 5,
        },
    )

    # Cancelled arrives BEFORE Approved
    async with session_factory() as session:
        await handle_payroll_event(session, cancelled_evt)
        await session.commit()

    async with session_factory() as session:
        await handle_payroll_event(session, approved_evt)
        await session.commit()

    # Verify no deduction created
    async with session_factory() as session:
        res = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
        assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_p3_leave_cancelled_duplicate_harmless(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    leave_id = uuid4()
    cancelled_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_CANCELLED,
        correlation_id=uuid4(),
        payload={"leave_id": str(leave_id), "employee_id": str(uuid4())},
    )

    async with session_factory() as session:
        await handle_payroll_event(session, cancelled_evt)
        await session.commit()

    async with session_factory() as session:
        await handle_payroll_event(session, cancelled_evt)
        await session.commit()


@pytest.mark.asyncio
async def test_p4_leave_cancelled_unknown_leave_id_harmless(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    unknown_leave_id = uuid4()
    cancelled_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_CANCELLED,
        correlation_id=uuid4(),
        payload={"leave_id": str(unknown_leave_id), "employee_id": str(uuid4())},
    )

    async with session_factory() as session:
        await handle_payroll_event(session, cancelled_evt)
        await session.commit()


@pytest.mark.asyncio
async def test_p5_dispatcher_ignores_unrelated_event(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    unrelated_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.EMPLOYEE_ONBOARDED,
        correlation_id=uuid4(),
        payload={"employee_id": str(uuid4()), "name": "Jane"},
    )

    async with session_factory() as session:
        await handle_payroll_event(session, unrelated_evt)
        await session.commit()


@pytest.mark.asyncio
async def test_p6_leave_approved_duplicate_event_id(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    event_id = uuid4()
    leave_id = uuid4()
    emp_id = uuid4()

    approved_evt = EventEnvelope(
        event_id=event_id,
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(emp_id),
            "start_date": "2024-08-05",
            "end_date": "2024-08-09",
            "leave_type": "UNPAID",
            "days": 5,
        },
    )

    async with session_factory() as session:
        await handle_payroll_event(session, approved_evt)
        await session.commit()

    async with session_factory() as session:
        await handle_payroll_event(session, approved_evt)
        await session.commit()

    async with session_factory() as session:
        res = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
        rows = list(res.scalars().all())
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_p7_paid_leave_approved_no_deduction(setup_db_and_app):
    from services.payroll.app.consumer_handler import handle_payroll_event
    session_factory = setup_db_and_app
    leave_id = uuid4()

    paid_evt = EventEnvelope(
        event_id=uuid4(),
        type=EventType.LEAVE_APPROVED,
        correlation_id=uuid4(),
        payload={
            "leave_id": str(leave_id),
            "employee_id": str(uuid4()),
            "start_date": "2024-09-02",
            "end_date": "2024-09-06",
            "leave_type": "PAID",
            "days": 5,
        },
    )

    async with session_factory() as session:
        await handle_payroll_event(session, paid_evt)
        await session.commit()

    async with session_factory() as session:
        res = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
        assert res.scalar_one_or_none() is None


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
async def test_p8_e2e_rabbitmq_payroll_consumer(setup_db_and_app, rabbitmq_url):
    import asyncio
    import aio_pika
    from ems_common.consumer import run_consumer
    from services.payroll.app.consumer_handler import handle_payroll_event

    session_factory = setup_db_and_app
    emp_id = uuid4()
    leave_id = uuid4()
    event_id = uuid4()

    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(
        run_consumer(
            rabbitmq_url=rabbitmq_url,
            exchange_name="ems.events",
            queue_name="payroll.e2e.test.queue",
            dlx_name="payroll.e2e.test.dlx",
            dlq_name="payroll.e2e.test.dlq",
            routing_keys=["LeaveApproved", "LeaveCancelled"],
            session_factory=session_factory,
            handler=handle_payroll_event,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.5)

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)

        envelope = EventEnvelope(
            event_id=event_id,
            type=EventType.LEAVE_APPROVED,
            correlation_id=uuid4(),
            payload={
                "leave_id": str(leave_id),
                "employee_id": str(emp_id),
                "start_date": "2024-10-07",
                "end_date": "2024-10-11",
                "leave_type": "UNPAID",
                "days": 5,
            },
        )
        msg_bytes = envelope.model_dump_json().encode("utf-8")
        await exchange.publish(
            aio_pika.Message(body=msg_bytes, headers={"X-Correlation-ID": str(uuid4())}),
            routing_key="LeaveApproved",
        )

    # Bounded wait loop (no fixed sleep)
    found = False
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < 10.0:
        async with session_factory() as session:
            res = await session.execute(select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id))
            deduction = res.scalar_one_or_none()
            if deduction:
                assert deduction.employee_id == emp_id
                found = True
                break
        await asyncio.sleep(0.2)

    stop_event.set()
    if consumer_task.done() and not consumer_task.cancelled():
        exc = consumer_task.exception()
        if exc:
            print("CONSUMER TASK EXCEPTION:", exc)
    consumer_task.cancel()
    try:
        await consumer_task
    except (Exception, asyncio.CancelledError):
        pass

    assert found is True
