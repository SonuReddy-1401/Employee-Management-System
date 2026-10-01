import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from ems_common.correlation import CORRELATION_ID_HEADER, CorrelationIdMiddleware, get_correlation_id

app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)


@app.get("/sample")
async def sample_endpoint():
    return {"correlation_id": get_correlation_id()}


@pytest.mark.asyncio
async def test_middleware_generates_correlation_id_when_missing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sample")
        assert response.status_code == 200
        corr_id = response.headers.get(CORRELATION_ID_HEADER)
        assert corr_id is not None
        assert len(corr_id) > 0
        assert response.json()["correlation_id"] == corr_id


@pytest.mark.asyncio
async def test_middleware_echoes_provided_correlation_id():
    custom_id = "custom-uuid-9999"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sample", headers={CORRELATION_ID_HEADER: custom_id})
        assert response.status_code == 200
        assert response.headers.get(CORRELATION_ID_HEADER) == custom_id
        assert response.json()["correlation_id"] == custom_id
