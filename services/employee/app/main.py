import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ems_common.correlation import CorrelationIdMiddleware
from ems_common.errors import register_error_handlers
from ems_common.observability import setup_observability
from ems_common.outbox import publish_outbox_messages
from services.employee.app.api.routes import get_db, router
from services.employee.app.config import settings
from services.employee.app.models.employee import Base

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


async def outbox_publisher_loop():
    while True:
        try:
            async with async_session_factory() as session:
                await publish_outbox_messages(session)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"Outbox publisher encountered error: {exc}")
        await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    publisher_task = None
    if settings.OUTBOX_PUBLISHER_ENABLED:
        publisher_task = asyncio.create_task(outbox_publisher_loop())

    yield

    if publisher_task:
        publisher_task.cancel()
        try:
            await publisher_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()


app = FastAPI(title="Employee Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)
setup_observability(app)

app.dependency_overrides[get_db] = get_db_override
app.include_router(router)
