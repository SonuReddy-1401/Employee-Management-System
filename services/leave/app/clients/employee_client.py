import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from ems_common.errors import EMSError
from ems_common.http_client import CircuitBreakerOpenError, ResilientHTTPClient
from services.leave.app.config import settings

logger = logging.getLogger(__name__)


class EmployeeClient:
    def __init__(
        self,
        employee_service_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        http_client: Optional[ResilientHTTPClient] = None,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.base_url = (employee_service_url or settings.EMPLOYEE_SERVICE_URL).rstrip("/")
        self.redis_url = redis_url or settings.REDIS_URL
        self.http_client = http_client or ResilientHTTPClient()
        self._redis = redis_client

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis is not None:
            return self._redis
        try:
            client = aioredis.from_url(self.redis_url, decode_responses=True)
            return client
        except Exception as exc:
            logger.warning(f"Failed to connect to Redis: {exc}")
            return None

    async def get_employee(self, employee_id: str, auth_header: str) -> Dict[str, Any]:
        cache_key = f"employee:{employee_id}"
        redis_conn = await self._get_redis()

        # Try Redis cache first
        if redis_conn is not None:
            try:
                cached = await redis_conn.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning(f"Redis cache read error: {exc}")

        # Cache miss or Redis error -> fetch from Employee Service
        url = f"{self.base_url}/employees/{employee_id}"
        headers = {"Authorization": auth_header} if auth_header else {}

        try:
            resp = await self.http_client.get(url, headers=headers)
        except CircuitBreakerOpenError:
            raise EMSError(
                code="EMPLOYEE_SERVICE_UNAVAILABLE",
                message="Employee service circuit breaker is open",
                status_code=503,
            )
        except Exception as exc:
            logger.warning(f"Employee service call failed: {exc}")
            raise EMSError(
                code="EMPLOYEE_SERVICE_UNAVAILABLE",
                message="Employee service is unreachable",
                status_code=503,
            )

        if resp.status_code == 404:
            raise EMSError(
                code="INVALID_EMPLOYEE",
                message=f"Employee {employee_id} not found",
                status_code=422,
            )

        if resp.status_code != 200:
            raise EMSError(
                code="EMPLOYEE_SERVICE_UNAVAILABLE",
                message=f"Employee service returned error status {resp.status_code}",
                status_code=503,
            )

        data = resp.json()
        if data.get("status") != "ACTIVE":
            raise EMSError(
                code="INVALID_EMPLOYEE",
                message=f"Employee {employee_id} is not in ACTIVE status",
                status_code=422,
            )

        cached_data = {
            "id": str(data["id"]),
            "status": data["status"],
            "manager_id": str(data["manager_id"]) if data.get("manager_id") else None,
        }

        # Save to Redis cache if available
        if redis_conn is not None:
            try:
                await redis_conn.setex(
                    cache_key,
                    settings.EMPLOYEE_CACHE_TTL_SECONDS,
                    json.dumps(cached_data),
                )
            except Exception as exc:
                logger.warning(f"Redis cache write error: {exc}")

        return cached_data
