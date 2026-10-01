import httpx
import pybreaker
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential
from ems_common.config import settings
from ems_common.correlation import CORRELATION_ID_HEADER, get_correlation_id
from ems_common.errors import EMSError


class CircuitBreakerOpenError(EMSError):
    def __init__(self, message: str = "Circuit breaker is open"):
        super().__init__(code="CIRCUIT_BREAKER_OPEN", message=message, status_code=503)


def is_retriable_exception(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def create_circuit_breaker(fail_max: int = None, reset_timeout: float = None) -> pybreaker.CircuitBreaker:
    return pybreaker.CircuitBreaker(
        fail_max=fail_max or settings.HTTP_CLIENT_BREAKER_FAIL_THRESHOLD,
        reset_timeout=reset_timeout or settings.HTTP_CLIENT_BREAKER_RESET_TIMEOUT_SECONDS,
    )


class ResilientHTTPClient:
    def __init__(self, client: httpx.AsyncClient = None, breaker: pybreaker.CircuitBreaker = None):
        self._client = client or httpx.AsyncClient(timeout=settings.HTTP_CLIENT_TIMEOUT_SECONDS)
        self._breaker = breaker or create_circuit_breaker()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._breaker.current_state == pybreaker.STATE_OPEN:
            raise CircuitBreakerOpenError()

        headers = kwargs.pop("headers", None) or {}
        corr_id = get_correlation_id()
        if corr_id:
            headers[CORRELATION_ID_HEADER] = corr_id

        async def _single_request():
            response = await self._client.request(method, url, headers=headers, **kwargs)
            if response.status_code >= 500:
                response.raise_for_status()
            return response

        async def _request_with_retry():
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(is_retriable_exception),
                stop=stop_after_attempt(settings.HTTP_CLIENT_RETRY_COUNT),
                wait=wait_exponential(multiplier=0.01),  # fast wait in client execution
                reraise=True,
            ):
                with attempt:
                    return await _single_request()

        try:
            result = await _request_with_retry()
            self._breaker.state._handle_success()
            return result
        except pybreaker.CircuitBreakerError:
            raise CircuitBreakerOpenError()
        except Exception as exc:
            try:
                self._breaker.state._handle_error(exc)
            except pybreaker.CircuitBreakerError:
                raise CircuitBreakerOpenError()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)
