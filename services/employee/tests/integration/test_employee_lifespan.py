import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.employee.app.main import app
from services.employee.app.config import settings


@pytest.mark.asyncio
async def test_employee_lifespan_publisher_enabled(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOX_PUBLISHER_ENABLED", True)

    mock_conn = AsyncMock()
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_begin.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_begin
    mock_engine.dispose = AsyncMock()

    monkeypatch.setattr("services.employee.app.main.engine", mock_engine)

    stub_called = False

    async def stub_outbox_publisher_loop():
        nonlocal stub_called
        stub_called = True
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            pass

    monkeypatch.setattr("services.employee.app.main.outbox_publisher_loop", stub_outbox_publisher_loop)

    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.1)
        assert stub_called is True
