import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from ems_common.config import settings as common_settings
from ems_common.security import decode_access_token
from services.gateway.app.config import settings
from services.gateway.app.main import app, rate_limiter
import jwt
from datetime import datetime, timedelta, timezone


def create_test_jwt(sub: str = "test-user-id", role: str = "ADMIN", expired: bool = False) -> str:
    exp = datetime.now(timezone.utc) + (
        timedelta(seconds=-10) if expired else timedelta(hours=1)
    )
    payload = {"sub": sub, "role": role, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.windows.clear()


@pytest.mark.asyncio
async def test_health_and_metrics_endpoints():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        res_metrics = await client.get("/metrics")
        assert res_metrics.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_prefix_routing_forwarding():
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    auth_route = respx.get(f"{settings.AUTH_SERVICE_URL}/auth/me").respond(200, json={"auth": "ok"})
    emp_route = respx.post(f"{settings.EMPLOYEE_SERVICE_URL}/employees").respond(201, json={"emp": "ok"})
    leave_route = respx.get(f"{settings.LEAVE_SERVICE_URL}/leaves?status=PENDING").respond(200, json={"leave": "ok"})
    payroll_route = respx.post(f"{settings.PAYROLL_SERVICE_URL}/payroll/run").respond(200, json={"payroll": "ok"})
    notification_route = respx.get(f"{settings.NOTIFICATION_SERVICE_URL}/notifications/123").respond(200, json={"notif": "ok"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.get("/auth/me", headers=headers)
        assert res1.status_code == 200
        assert res1.json() == {"auth": "ok"}
        assert auth_route.called

        res2 = await client.post("/employees", json={"name": "Alice"}, headers=headers)
        assert res2.status_code == 201
        assert res2.json() == {"emp": "ok"}
        assert emp_route.called

        res3 = await client.get("/leaves?status=PENDING", headers=headers)
        assert res3.status_code == 200
        assert res3.json() == {"leave": "ok"}
        assert leave_route.called

        res4 = await client.post("/payroll/run", headers=headers)
        assert res4.status_code == 200
        assert res4.json() == {"payroll": "ok"}
        assert payroll_route.called

        res5 = await client.get("/notifications/123", headers=headers)
        assert res5.status_code == 200
        assert res5.json() == {"notif": "ok"}
        assert notification_route.called


@pytest.mark.asyncio
@respx.mock
async def test_internal_endpoints_blocked_404():
    auth_route = respx.post(f"{settings.AUTH_SERVICE_URL}/internal/users").respond(200, json={"ok": True})
    payroll_route = respx.delete(f"{settings.PAYROLL_SERVICE_URL}/internal/profiles/123").respond(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/internal/users", json={"email": "test@test.com"})
        assert res1.status_code == 404
        assert res1.json()["error"]["code"] == "NOT_FOUND"
        assert auth_route.call_count == 0

        res2 = await client.delete("/internal/profiles/123")
        assert res2.status_code == 404
        assert res2.json()["error"]["code"] == "NOT_FOUND"
        assert payroll_route.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_authentication_enforcement():
    respx.post(f"{settings.AUTH_SERVICE_URL}/auth/login").respond(200, json={"access_token": "abc"})
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees").respond(200, json={"items": []})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # POST /auth/login works without token
        res_login = await client.post("/auth/login", json={"email": "a@b.com", "password": "pass"})
        assert res_login.status_code == 200

        # Protected endpoint without token -> 401
        res_no_token = await client.get("/employees")
        assert res_no_token.status_code == 401
        assert res_no_token.json()["error"]["code"] == "UNAUTHORIZED"

        # Invalid token -> 401
        res_invalid = await client.get("/employees", headers={"Authorization": "Bearer invalid.token.str"})
        assert res_invalid.status_code == 401

        # Expired token -> 401
        expired_token = create_test_jwt(expired=True)
        res_expired = await client.get("/employees", headers={"Authorization": f"Bearer {expired_token}"})
        assert res_expired.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_correlation_id_propagation():
    token = create_test_jwt()

    route = respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees").respond(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Provided correlation ID
        provided_cid = "custom-cid-12345"
        res = await client.get(
            "/employees",
            headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": provided_cid},
        )
        assert res.status_code == 200
        assert res.headers["X-Correlation-ID"] == provided_cid

        req_sent = route.calls.last.request
        assert req_sent.headers["X-Correlation-ID"] == provided_cid

        # Generated correlation ID when absent
        res_gen = await client.get("/employees", headers={"Authorization": f"Bearer {token}"})
        assert res_gen.status_code == 200
        assert "X-Correlation-ID" in res_gen.headers
        assert len(res_gen.headers["X-Correlation-ID"]) > 0


@pytest.mark.asyncio
@respx.mock
async def test_upstream_error_passthrough():
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/missing").respond(
        404, json={"error": {"code": "NOT_FOUND", "message": "Employee not found"}}
    )
    respx.post(f"{settings.EMPLOYEE_SERVICE_URL}/employees").respond(
        409, json={"error": {"code": "CONFLICT", "message": "Email exists"}}
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res404 = await client.get("/employees/missing", headers=headers)
        assert res404.status_code == 404
        assert res404.json()["error"]["code"] == "NOT_FOUND"

        res409 = await client.post("/employees", json={}, headers=headers)
        assert res409.status_code == 409
        assert res409.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
@respx.mock
async def test_upstream_connect_error_and_timeout():
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/conn-fail").side_effect = httpx.ConnectError("Connection refused")
    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees/timeout").side_effect = httpx.ReadTimeout("Timeout")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res_502 = await client.get("/employees/conn-fail", headers=headers)
        assert res_502.status_code == 502
        assert res_502.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"

        res_504 = await client.get("/employees/timeout", headers=headers)
        assert res_504.status_code == 504
        assert res_504.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


@pytest.mark.asyncio
@respx.mock
async def test_rate_limiting_and_login_limit():
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    respx.get(f"{settings.EMPLOYEE_SERVICE_URL}/employees").respond(200, json={"ok": True})
    respx.post(f"{settings.AUTH_SERVICE_URL}/auth/login").respond(200, json={"token": "ok"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Exceed login rate limit (stricter limit = 10)
        for _ in range(settings.LOGIN_RATE_LIMIT_REQUESTS):
            res = await client.post("/auth/login", json={"email": "a@b.com", "password": "p"})
            assert res.status_code == 200

        res_blocked_login = await client.post("/auth/login", json={"email": "a@b.com", "password": "p"})
        assert res_blocked_login.status_code == 429
        assert res_blocked_login.headers.get("Retry-After") is not None
        assert res_blocked_login.json()["error"]["code"] == "RATE_LIMITED"

        # /health and /metrics remain exempt
        res_health = await client.get("/health")
        assert res_health.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_no_retry_on_failed_upstream_post():
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    route = respx.post(f"{settings.EMPLOYEE_SERVICE_URL}/employees").respond(500, json={"error": "failed"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/employees", json={"name": "Bob"}, headers=headers)
        assert res.status_code == 500
        assert route.call_count == 1
