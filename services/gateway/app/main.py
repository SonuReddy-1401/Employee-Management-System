from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ems_common.correlation import CorrelationIdMiddleware
from ems_common.errors import EMSError, register_error_handlers
from ems_common.observability import setup_observability
from ems_common.security import decode_access_token
from services.gateway.app.config import settings
from services.gateway.app.domain.gateway import RateLimiter, is_blocked, is_public, resolve_upstream
from services.gateway.app.proxy.client import proxy_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT_SECONDS)
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(title="EMS API Gateway", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)
setup_observability(app)

rate_limiter = RateLimiter()


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def gateway_router(request: Request, path: str):
    full_path = request.url.path

    if is_blocked(full_path):
        raise EMSError(code="NOT_FOUND", message="Resource not found", status_code=404)

    client_ip = request.client.host if request.client else "127.0.0.1"

    if full_path.rstrip("/") == "/auth/login":
        limit = settings.LOGIN_RATE_LIMIT_REQUESTS
        prefix = "login"
    else:
        limit = settings.RATE_LIMIT_REQUESTS
        prefix = "general"

    allowed, retry_after = rate_limiter.is_allowed(
        client_ip, prefix, limit, settings.RATE_LIMIT_WINDOW_SECONDS
    )
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "Rate limit exceeded"}},
            headers={"Retry-After": str(retry_after)},
        )

    if not is_public(request.method, full_path):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise EMSError(
                code="UNAUTHORIZED",
                message="Missing or invalid authorization header",
                status_code=401,
            )
        token = auth_header.split(" ")[1]
        decode_access_token(token)

    resolved = resolve_upstream(full_path)
    if not resolved:
        raise EMSError(code="NOT_FOUND", message="Resource not found", status_code=404)

    upstream_url, _ = resolved

    http_client = getattr(request.app.state, "http_client", None)
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT_SECONDS)
        request.app.state.http_client = http_client

    return await proxy_request(http_client, upstream_url, request)
