import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ems_common.correlation import CorrelationIdMiddleware
from ems_common.errors import register_error_handlers
from ems_common.observability import setup_observability
from ems_common.outbox import OutboxBase, publish_outbox_messages

from services.leave.app.api.routes import router
from services.leave.app.clients.employee_client import EmployeeClient
from services.leave.app.config import settings
from services.leave.app.models.leave import Base

logger = logging.getLogger(__name__)


async def outbox_publisher_loop(session_factory, rabbitmq_url: str):
    while True:
        try:
            async with session_factory() as session:
                await publish_outbox_messages(session, rabbitmq_url=rabbitmq_url)
        except Exception as exc:
            logger.warning(f"Outbox publisher iteration error: {exc}")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.state.engine = engine
    app.state.session_factory = session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(OutboxBase.metadata.create_all)

    # Initialize EmployeeClient
    app.state.employee_client = EmployeeClient(
        employee_service_url=settings.EMPLOYEE_SERVICE_URL,
        redis_url=settings.REDIS_URL,
    )

    publisher_task = None
    if settings.OUTBOX_PUBLISHER_ENABLED:
        publisher_task = asyncio.create_task(
            outbox_publisher_loop(session_factory, settings.RABBITMQ_URL)
        )

    yield

    if publisher_task:
        publisher_task.cancel()
        try:
            await publisher_task
        except asyncio.CancelledError:
            pass

    await engine.dispose()


app = FastAPI(title="EMS Leave Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)
setup_observability(app)

app.include_router(router)
