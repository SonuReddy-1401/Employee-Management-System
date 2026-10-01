import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from ems_common.errors import EMSError, register_error_handlers

app = FastAPI()
register_error_handlers(app)


class SampleSchema(BaseModel):
    name: str
    age: int


@app.get("/custom-error")
async def custom_error_route():
    raise EMSError(code="BUSINESS_RULE_VIOLATION", message="Custom error occurred", status_code=400)


@app.get("/http-404")
async def http_404_route():
    raise HTTPException(status_code=404, detail="Resource not found")


@app.post("/validation")
async def validation_route(payload: SampleSchema):
    return payload


@app.get("/unexpected")
async def unexpected_route():
    raise RuntimeError("Unexpected failure")


@pytest.mark.asyncio
async def test_custom_ems_error_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/custom-error")
        assert res.status_code == 400
        assert res.json() == {"error": {"code": "BUSINESS_RULE_VIOLATION", "message": "Custom error occurred"}}


@pytest.mark.asyncio
async def test_http_exception_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/http-404")
        assert res.status_code == 404
        assert res.json() == {"error": {"code": "NOT_FOUND", "message": "Resource not found"}}


@pytest.mark.asyncio
async def test_validation_error_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/validation", json={"name": "Alice", "age": "not-an-int"})
        assert res.status_code == 422
        json_resp = res.json()
        assert "error" in json_resp
        assert json_resp["error"]["code"] == "VALIDATION_ERROR"
        assert "Input should be a valid integer" in json_resp["error"]["message"]


@pytest.mark.asyncio
async def test_unexpected_error_format():
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        res = await client.get("/unexpected")
        assert res.status_code == 500
        assert res.json() == {
            "error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred."}
        }
