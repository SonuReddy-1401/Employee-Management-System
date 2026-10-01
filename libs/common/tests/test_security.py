from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from ems_common.config import settings
from ems_common.errors import register_error_handlers
from ems_common.security import require_roles

app = FastAPI()
register_error_handlers(app)


@app.get("/admin-only")
async def admin_only_endpoint(user: dict = Depends(require_roles("ADMIN", "HR"))):
    return {"status": "ok", "user": user}


def create_token(sub: str, role: str, exp_delta: timedelta = timedelta(hours=1)) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.mark.asyncio
async def test_valid_jwt_token_passes():
    token = create_token("user-1", "ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["user"]["user_id"] == "user-1"
        assert res.json()["user"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_expired_jwt_token_returns_401():
    token = create_token("user-1", "ADMIN", exp_delta=timedelta(seconds=-10))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert res.json() == {"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired"}}


@pytest.mark.asyncio
async def test_tampered_jwt_token_returns_401():
    token = create_token("user-1", "ADMIN") + "tampered"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert res.json() == {"error": {"code": "INVALID_TOKEN", "message": "Invalid token"}}


@pytest.mark.asyncio
async def test_wrong_role_returns_403():
    token = create_token("user-1", "EMPLOYEE")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"
        assert "EMPLOYEE" in res.json()["error"]["message"]
