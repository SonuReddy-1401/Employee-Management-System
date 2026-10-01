import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.payroll.app.main import app
from services.payroll.app.config import settings


@pytest.mark.asyncio
async def test_payroll_lifespan_consumer_enabled(monkeypatch):
    monkeypatch.setattr(settings, "CONSUMER_ENABLED", True)

    mock_conn = AsyncMock()
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_begin.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_begin
    mock_engine.dispose = AsyncMock()

    monkeypatch.setattr("services.payroll.app.main.engine", mock_engine)

    stub_called = False
    stop_event_received = False

    async def stub_run_consumer(*args, **kwargs):
        nonlocal stub_called, stop_event_received
        stub_called = True
        stop_event = kwargs.get("stop_event")
        if stop_event:
            while not stop_event.is_set():
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    break
            stop_event_received = True

    with patch("ems_common.consumer.run_consumer", side_effect=stub_run_consumer):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.1)
            assert stub_called is True

    assert stop_event_received is True
