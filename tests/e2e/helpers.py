import calendar
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import httpx
from tests.e2e.config import (
    E2E_WAIT_TIMEOUT_SECONDS,
    GATEWAY_URL,
    RABBITMQ_MGMT_PASSWORD,
    RABBITMQ_MGMT_URL,
    RABBITMQ_MGMT_USER,
)

RATE_LIMIT_WARNINGS = []


def unique_email(prefix: str = "e2e") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:6]}@e2e.test.com"


class E2EClient:
    def __init__(self, base_url: str = GATEWAY_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=15.0)
        self.token = None

    def login(self, email: str, password: str) -> str:
        resp = self.request("POST", "/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200 and "access_token" in resp.json():
            self.token = resp.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {self.token}"
            return self.token
        else:
            raise RuntimeError(f"Login failed for {email}: status {resp.status_code}, body {resp.text}")

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        resp = self.client.request(method, url, **kwargs)
        while resp.status_code == 429:
            retry_after_str = resp.headers.get("Retry-After", "2")
            try:
                retry_after = float(retry_after_str)
            except ValueError:
                retry_after = 2.0
            retry_after = max(retry_after, 2.0)
            warning_msg = f"[RATE LIMIT WARNING] HTTP 429 hit for {method} {url}. Retrying after {retry_after}s..."
            print(warning_msg)
            RATE_LIMIT_WARNINGS.append(warning_msg)
            time.sleep(retry_after)
            resp = self.client.request(method, url, **kwargs)
        return resp


    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def close(self):
        self.client.close()


def wait_until(condition_fn, timeout: int = E2E_WAIT_TIMEOUT_SECONDS, interval: float = 2.0, message: str = "Condition not met"):

    start_time = time.time()
    while time.time() - start_time < timeout:
        res = condition_fn()
        if res:
            return res
        time.sleep(interval)
    raise AssertionError(f"Timeout ({timeout}s): {message}")


def wait_queue_drained(queue_name: str, timeout: int = E2E_WAIT_TIMEOUT_SECONDS):
    mgmt_url = f"{RABBITMQ_MGMT_URL.rstrip('/')}/api/queues/%2F/{queue_name}"
    auth = (RABBITMQ_MGMT_USER, RABBITMQ_MGMT_PASSWORD)

    def check_queue():
        try:
            with httpx.Client(timeout=5.0) as mgmt_client:
                r = mgmt_client.get(mgmt_url, auth=auth)
                if r.status_code == 200:
                    q_data = r.json()
                    ready = q_data.get("messages_ready", 0)
                    unack = q_data.get("messages_unacknowledged", 0)
                    return ready == 0 and unack == 0
        except Exception:
            pass
        return False

    wait_until(check_queue, timeout=timeout, message=f"Queue {queue_name} was not drained (0 ready, 0 unack)")


def first_monday(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != 0:  # 0 is Monday
        d += timedelta(days=1)
    return d


def count_weekdays(year: int, month: int) -> int:
    num_days = calendar.monthrange(year, month)[1]
    count = 0
    for day in range(1, num_days + 1):
        if date(year, month, day).weekday() < 5:  # 0-4 are Mon-Fri
            count += 1
    return count


def compute_payslip_deduction(monthly_salary: float, year: int, month: int, unpaid_days: int):
    gross = Decimal(str(monthly_salary))
    working_days = Decimal(count_weekdays(year, month))
    unpaid = Decimal(unpaid_days)
    if working_days == Decimal(0) or unpaid == Decimal(0):
        deduction = Decimal("0.00")
    else:
        deduction = (gross / working_days * unpaid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net_salary = gross - deduction
    return deduction, net_salary
