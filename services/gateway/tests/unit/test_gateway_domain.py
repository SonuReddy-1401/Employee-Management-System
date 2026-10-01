from services.gateway.app.config import settings
from services.gateway.app.domain.gateway import RateLimiter, is_blocked, is_public, resolve_upstream


def test_resolve_upstream_prefixes():
    assert resolve_upstream("/auth/login")[0] == settings.AUTH_SERVICE_URL
    assert resolve_upstream("/employees/123")[0] == settings.EMPLOYEE_SERVICE_URL
    assert resolve_upstream("/leaves/balance")[0] == settings.LEAVE_SERVICE_URL
    assert resolve_upstream("/payroll/run")[0] == settings.PAYROLL_SERVICE_URL
    assert resolve_upstream("/payslips/456")[0] == settings.PAYROLL_SERVICE_URL
    assert resolve_upstream("/notifications/789")[0] == settings.NOTIFICATION_SERVICE_URL


def test_resolve_upstream_exact_match():
    assert resolve_upstream("/employees")[0] == settings.EMPLOYEE_SERVICE_URL


def test_resolve_upstream_prefix_isolation():
    assert resolve_upstream("/employeesX") is None
    assert resolve_upstream("/authX") is None
    assert resolve_upstream("/unknown") is None


def test_is_blocked():
    assert is_blocked("/internal") is True
    assert is_blocked("/internal/users") is True
    assert is_blocked("/internal/anything/else") is True
    assert is_blocked("/employees") is False
    assert is_blocked("/auth/login") is False


def test_is_public():
    assert is_public("POST", "/auth/login") is True
    assert is_public("POST", "/auth/login/") is True
    assert is_public("GET", "/health") is True
    assert is_public("GET", "/metrics") is True
    assert is_public("GET", "/auth/login") is False
    assert is_public("GET", "/employees") is False


def test_rate_limiter_allows_then_blocks():
    current_time = 1000.0

    def fake_clock():
        return current_time

    limiter = RateLimiter(clock=fake_clock)

    # Allow 2 requests
    allowed1, _ = limiter.is_allowed("1.2.3.4", "test", 2, 60)
    allowed2, _ = limiter.is_allowed("1.2.3.4", "test", 2, 60)
    assert allowed1 is True
    assert allowed2 is True

    # 3rd request blocked
    allowed3, retry_after = limiter.is_allowed("1.2.3.4", "test", 2, 60)
    assert allowed3 is False
    assert retry_after == 60


def test_rate_limiter_window_reset():
    current_time = 1000.0

    def fake_clock():
        return current_time

    limiter = RateLimiter(clock=fake_clock)

    limiter.is_allowed("1.2.3.4", "test", 1, 60)
    allowed, _ = limiter.is_allowed("1.2.3.4", "test", 1, 60)
    assert allowed is False

    # Advance time by 61 seconds
    current_time = 1061.0
    allowed_after_window, _ = limiter.is_allowed("1.2.3.4", "test", 1, 60)
    assert allowed_after_window is True


def test_rate_limiter_separate_keys_per_client():
    limiter = RateLimiter(clock=lambda: 1000.0)

    allowed_ip1, _ = limiter.is_allowed("1.1.1.1", "test", 1, 60)
    allowed_ip2, _ = limiter.is_allowed("2.2.2.2", "test", 1, 60)

    assert allowed_ip1 is True
    assert allowed_ip2 is True

    blocked_ip1, _ = limiter.is_allowed("1.1.1.1", "test", 1, 60)
    assert blocked_ip1 is False


def test_rate_limiter_cleanup_expired():
    current_time = 1000.0

    def fake_clock():
        return current_time

    limiter = RateLimiter(clock=fake_clock)
    limiter.is_allowed("1.1.1.1", "test", 1, 60)
    assert len(limiter.windows) == 1

    current_time = 1070.0
    limiter.cleanup_expired(60)
    assert len(limiter.windows) == 0
