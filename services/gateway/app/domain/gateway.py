import time
from typing import Callable, Dict, Optional, Tuple
from services.gateway.app.config import settings


def resolve_upstream(path: str) -> Optional[Tuple[str, str]]:
    routes = [
        ("/auth", settings.AUTH_SERVICE_URL),
        ("/employees", settings.EMPLOYEE_SERVICE_URL),
        ("/leaves", settings.LEAVE_SERVICE_URL),
        ("/payroll", settings.PAYROLL_SERVICE_URL),
        ("/payslips", settings.PAYROLL_SERVICE_URL),
        ("/notifications", settings.NOTIFICATION_SERVICE_URL),
    ]

    for prefix, target_url in routes:
        if path == prefix or path.startswith(prefix + "/"):
            return target_url, path

    return None


def is_blocked(path: str) -> bool:
    return path == "/internal" or path.startswith("/internal/")


def is_public(method: str, path: str) -> bool:
    clean_path = path.rstrip("/")
    if method.upper() == "POST" and clean_path == "/auth/login":
        return True
    if clean_path in ("/health", "/metrics", ""):
        return True
    return False


class RateLimiter:

    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self.clock = clock if clock is not None else time.time
        self.windows: Dict[str, Tuple[float, int]] = {}

    def is_allowed(
        self, client_ip: str, key_prefix: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
        now = self.clock()
        self.cleanup_expired(window_seconds)

        key = f"{key_prefix}:{client_ip}"
        if key in self.windows:
            window_start, count = self.windows[key]
            if now - window_start < window_seconds:
                if count < max_requests:
                    self.windows[key] = (window_start, count + 1)
                    return True, 0
                else:
                    retry_after = max(1, int(window_seconds - (now - window_start)))
                    return False, retry_after

        # Start new window
        self.windows[key] = (now, 1)
        return True, 0

    def cleanup_expired(self, window_seconds: int) -> None:
        now = self.clock()
        expired_keys = [
            k for k, (start, _) in self.windows.items() if now - start >= window_seconds
        ]
        for k in expired_keys:
            del self.windows[k]
