import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ems_common.correlation import CorrelationIdMiddleware
from ems_common.errors import register_error_handlers
from ems_common.observability import setup_observability
from services.payroll.app.api.routes import get_db, router
from services.payroll.app.config import settings
from services.payroll.app.models.payroll import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_override():
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stop_event = asyncio.Event()
    consumer_task = None
    if settings.CONSUMER_ENABLED:
        import asyncio
        from ems_common.consumer import run_consumer
        from services.payroll.app.consumer_handler import handle_payroll_event
        consumer_task = asyncio.create_task(
            run_consumer(
                rabbitmq_url=settings.RABBITMQ_URL,
                exchange_name=settings.RABBITMQ_EXCHANGE,
                queue_name=settings.PAYROLL_QUEUE_NAME,
                dlx_name=settings.PAYROLL_DLX_NAME,
                dlq_name=settings.PAYROLL_DLQ_NAME,
                routing_keys=["LeaveApproved", "LeaveCancelled"],
                session_factory=async_session_factory,
                handler=handle_payroll_event,
                stop_event=stop_event,
            )
        )
    yield
    if consumer_task:
        stop_event.set()
        consumer_task.cancel()
        try:
            await consumer_task
        except (Exception, asyncio.CancelledError):
            pass
    await engine.dispose()


app = FastAPI(title="Payroll Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)
setup_observability(app)

app.dependency_overrides[get_db] = get_db_override
app.include_router(router)
