import uuid
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id_ctx.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        corr_id = request.headers.get(CORRELATION_ID_HEADER)
        if not corr_id:
            corr_id = str(uuid.uuid4())

        token = _correlation_id_ctx.set(corr_id)
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = corr_id
            return response
        finally:
            _correlation_id_ctx.reset(token)
