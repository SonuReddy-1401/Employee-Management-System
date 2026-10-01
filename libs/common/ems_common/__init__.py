from ems_common.config import settings
from ems_common.correlation import CorrelationIdMiddleware, get_correlation_id, set_correlation_id
from ems_common.errors import EMSError, register_error_handlers
from ems_common.events import EventEnvelope, EventType
from ems_common.http_client import CircuitBreakerOpenError, ResilientHTTPClient
from ems_common.logging import setup_logging
from ems_common.observability import setup_observability
from ems_common.security import decode_access_token, get_current_user, require_roles

__all__ = [
    "settings",
    "CorrelationIdMiddleware",
    "get_correlation_id",
    "set_correlation_id",
    "EMSError",
    "register_error_handlers",
    "EventEnvelope",
    "EventType",
    "CircuitBreakerOpenError",
    "ResilientHTTPClient",
    "setup_logging",
    "setup_observability",
    "decode_access_token",
    "get_current_user",
    "require_roles",
]
