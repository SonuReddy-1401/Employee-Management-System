import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.leave.app.main import app
from services.leave.app.config import settings


@pytest.mark.asyncio
async def test_leave_lifespan_publisher_enabled(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOX_PUBLISHER_ENABLED", True)

    mock_conn = AsyncMock()
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_begin.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_begin
    mock_engine.dispose = AsyncMock()

    monkeypatch.setattr("services.leave.app.main.create_async_engine", lambda *args, **kwargs: mock_engine)
    monkeypatch.setattr("services.leave.app.main.EmployeeClient", MagicMock())

    stub_called = False

    async def stub_outbox_publisher_loop(*args, **kwargs):
        nonlocal stub_called
        stub_called = True

        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            pass

    monkeypatch.setattr("services.leave.app.main.outbox_publisher_loop", stub_outbox_publisher_loop)

    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.1)
        assert stub_called is True
