import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ems_common.correlation import CorrelationIdMiddleware
from ems_common.errors import register_error_handlers
from ems_common.observability import setup_observability
from services.notification.app.api.routes import router
from services.notification.app.config import settings
from services.notification.app.models.notification import Base, ConsumerBase

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_factory = async_session_factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ConsumerBase.metadata.create_all)

    stop_event = asyncio.Event()
    consumer_task = None
    if settings.CONSUMER_ENABLED:
        from ems_common.consumer import run_consumer
        from services.notification.app.consumer_handler import handle_notification_event

        consumer_task = asyncio.create_task(
            run_consumer(
                rabbitmq_url=settings.RABBITMQ_URL,
                exchange_name=settings.RABBITMQ_EXCHANGE,
                queue_name=settings.NOTIFICATION_QUEUE_NAME,
                dlx_name=settings.NOTIFICATION_DLX_NAME,
                dlq_name=settings.NOTIFICATION_DLQ_NAME,
                routing_keys=[
                    "EmployeeOnboarded",
                    "LeaveRequested",
                    "LeaveApproved",
                    "LeaveRejected",
                    "LeaveCancelled",
                ],
                session_factory=async_session_factory,
                handler=handle_notification_event,
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


app = FastAPI(title="Notification Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)
setup_observability(app)

app.include_router(router)
