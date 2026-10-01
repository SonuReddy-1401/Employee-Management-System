import logging
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ems_common.correlation import CorrelationIdMiddleware
from ems_common.errors import register_error_handlers
from ems_common.observability import setup_observability
from services.auth.app.api.routes import get_db, router
from services.auth.app.config import settings
from services.auth.app.domain.auth import hash_password
from services.auth.app.models.user import Base, User
from services.auth.app.repositories.user_repository import UserRepository

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


async def seed_admin(session: AsyncSession):
    repo = UserRepository(session)
    if not await repo.has_admin_user():
        if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
            admin_user = User(
                id=uuid4(),
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="ADMIN",
            )
            await repo.create(admin_user)
            logger.info(f"Seeded admin user '{settings.ADMIN_EMAIL}' successfully.")
        else:
            logger.warning(
                "No admin user found, and ADMIN_EMAIL/ADMIN_PASSWORD environment variables are missing. Skipping admin seed."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await seed_admin(session)

    yield

    await engine.dispose()


app = FastAPI(title="Auth Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)
setup_observability(app)

app.dependency_overrides[get_db] = get_db_override
app.include_router(router)
