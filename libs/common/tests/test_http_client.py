import httpx
import pytest
import respx
from ems_common.correlation import CORRELATION_ID_HEADER, set_correlation_id
from ems_common.http_client import CircuitBreakerOpenError, ResilientHTTPClient, create_circuit_breaker


@pytest.mark.asyncio
@respx.mock
async def test_http_client_retry_on_503_then_success():
    route = respx.get("http://api.internal/data")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"status": "ok"}),
    ]

    async with ResilientHTTPClient() as client:
        res = await client.get("http://api.internal/data")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
        assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_http_client_no_retry_on_404():
    route = respx.get("http://api.internal/missing").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )

    async with ResilientHTTPClient() as client:
        res = await client.get("http://api.internal/missing")
        assert res.status_code == 404
        assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_http_client_forwards_correlation_id_header():
    set_correlation_id("corr-id-xyz-123")
    route = respx.get("http://api.internal/header-test").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    async with ResilientHTTPClient() as client:
        res = await client.get("http://api.internal/header-test")
        assert res.status_code == 200
        assert route.call_count == 1
        last_request = route.calls.last.request
        assert last_request.headers.get(CORRELATION_ID_HEADER) == "corr-id-xyz-123"


@pytest.mark.asyncio
@respx.mock
async def test_http_client_circuit_breaker_opens_after_failures():
    breaker = create_circuit_breaker(fail_max=2, reset_timeout=60.0)
    respx.get("http://api.internal/fail").mock(return_value=httpx.Response(500))

    async with ResilientHTTPClient(breaker=breaker) as client:
        # Call 1: fails with HTTPStatusError (fail_counter = 1)
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("http://api.internal/fail")

        # Call 2: fails with HTTPStatusError, trips breaker (fail_counter = 2), raises CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await client.get("http://api.internal/fail")

        # Call 3: fast fail (circuit open)
        with pytest.raises(CircuitBreakerOpenError):
            await client.get("http://api.internal/fail")
