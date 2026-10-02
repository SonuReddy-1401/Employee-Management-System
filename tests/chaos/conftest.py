import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
import httpx
import pytest
import pytest_asyncio
import aio_pika
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

AUTH_URL = os.getenv("CHAOS_AUTH_URL", os.getenv("CONTRACT_AUTH_URL", "http://localhost:8001"))
EMPLOYEE_URL = os.getenv("CHAOS_EMPLOYEE_URL", os.getenv("CONTRACT_EMPLOYEE_URL", "http://localhost:8002"))
LEAVE_URL = os.getenv("CHAOS_LEAVE_URL", os.getenv("CONTRACT_LEAVE_URL", "http://localhost:8003"))
PAYROLL_URL = os.getenv("CHAOS_PAYROLL_URL", os.getenv("CONTRACT_PAYROLL_URL", "http://localhost:8004"))
NOTIFICATION_URL = os.getenv("CHAOS_NOTIFICATION_URL", os.getenv("CONTRACT_NOTIFICATION_URL", "http://localhost:8005"))
GATEWAY_URL = os.getenv("CHAOS_GATEWAY_URL", os.getenv("CONTRACT_GATEWAY_URL", "http://localhost:8000"))
PROMETHEUS_URL = os.getenv("CHAOS_PROMETHEUS_URL", "http://localhost:9090")

RABBITMQ_HOST = os.getenv("CHAOS_RABBITMQ_HOST", os.getenv("CONTRACT_RABBITMQ_HOST", "localhost"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
RABBITMQ_USER = os.getenv("RABBITMQ_MGMT_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_MGMT_PASSWORD", "guest")

ALL_SERVICES = [
    "gateway",
    "auth",
    "employee",
    "leave",
    "payroll",
    "notification",
    "rabbitmq",
    "redis"
]

HTTP_SERVICES = {
    "gateway": GATEWAY_URL,
    "auth": AUTH_URL,
    "employee": EMPLOYEE_URL,
    "leave": LEAVE_URL,
    "payroll": PAYROLL_URL,
    "notification": NOTIFICATION_URL,
}


def pytest_configure(config):
    config.addinivalue_line("markers", "chaos: mark test as a chaos test")


def run_compose_cmd(cmd_args: list[str]) -> subprocess.CompletedProcess:
    full_cmd = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"] + cmd_args
    return subprocess.run(full_cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class DockerComposeHelper:
    def __init__(self):
        self.stopped_services = set()

    def stop(self, service: str):
        res = run_compose_cmd(["stop", service])
        if res.returncode != 0:
            raise RuntimeError(f"Failed to stop service {service}: {res.stderr}")
        self.stopped_services.add(service)

    def start(self, service: str):
        res = run_compose_cmd(["start", service])
        if res.returncode != 0:
            raise RuntimeError(f"Failed to start service {service}: {res.stderr}")
        if service in self.stopped_services:
            self.stopped_services.remove(service)

    def is_healthy(self, service: str) -> bool:
        if service in HTTP_SERVICES:
            url = HTTP_SERVICES[service]
            try:
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(f"{url}/health")
                    return resp.status_code == 200
            except Exception:
                return False
        else:
            # rabbitmq or redis check via docker compose ps
            res = run_compose_cmd(["ps", service])
            out = res.stdout.lower()
            return ("running" in out or "healthy" in out) and "exited" not in out

    def wait_healthy(self, service: str, timeout: float = 60.0):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_healthy(service):
                return True
            time.sleep(1.0)
        raise TimeoutError(f"Service {service} did not become healthy within {timeout} seconds.")

    def restore_all(self):
        for service in list(self.stopped_services):
            try:
                self.start(service)
                self.wait_healthy(service, timeout=30.0)
            except Exception:
                pass
        self.stopped_services.clear()


@pytest.fixture(scope="session", autouse=True)
def check_stack_health_session():
    helper = DockerComposeHelper()
    unhealthy = []
    for s in ALL_SERVICES:
        if not helper.is_healthy(s):
            unhealthy.append(s)
    if unhealthy:
        pytest.fail(
            f"Start the stack before running chaos tests: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait. "
            f"Unhealthy services at session start: {', '.join(unhealthy)}"
        )


@pytest.fixture(scope="session", autouse=True)
def restore_stack_finalizer():
    yield
    # Session cleanup to ensure stack is completely restored
    run_compose_cmd(["start"] + ALL_SERVICES)
    helper = DockerComposeHelper()
    for s in ALL_SERVICES:
        try:
            helper.wait_healthy(s, timeout=60.0)
        except Exception:
            pass


@pytest.fixture
def docker_compose():
    helper = DockerComposeHelper()
    try:
        yield helper
    finally:
        helper.restore_all()


def login_user_directly(email: str, password: str) -> str:
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(f"{AUTH_URL}/auth/login", json={"email": email, "password": password})
        if resp.status_code != 200:
            raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
        return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token() -> str:
    return login_user_directly(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def new_employee(admin_token):
    def _create_employee(department: str | None = None, role: str = "EMPLOYEE", manager_id: str | None = None) -> dict:
        emp_uuid = uuid.uuid4().hex[:6]
        email = f"chaos.{emp_uuid}@test.com"
        password = "Password123!"
        dept = department or f"ChaosDept-{emp_uuid}"
        payload = {
            "name": f"Chaos Employee {emp_uuid}",
            "email": email,
            "department": dept,
            "designation": "Chaos Tester",
            "initial_password": password,
            "monthly_salary": 30000.0,
            "role": role,
        }
        if manager_id:
            payload["manager_id"] = str(manager_id)

        headers = {"Authorization": f"Bearer {admin_token}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{EMPLOYEE_URL}/employees", json=payload, headers=headers)
            if resp.status_code != 201:
                raise RuntimeError(f"Failed to create employee: {resp.status_code} {resp.text}")
            emp_data = resp.json()
            emp_data["initial_password"] = password
            return emp_data

    return _create_employee


class EventListener:
    def __init__(self):
        self.events = []
        self._task = None
        self._connection = None
        self._channel = None

    async def start(self):
        amqp_url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:5672/"
        self._connection = await aio_pika.connect_robust(amqp_url)
        self._channel = await self._connection.channel()
        exchange = await self._channel.declare_exchange("ems.events", aio_pika.ExchangeType.TOPIC, durable=True)
        queue_name = f"chaos.queue.{uuid.uuid4().hex}"
        queue = await self._channel.declare_queue(queue_name, exclusive=True, auto_delete=True)
        await queue.bind(exchange, routing_key="#")

        async def _consumer():
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = json.loads(message.body.decode("utf-8"))
                            self.events.append({
                                "routing_key": message.routing_key,
                                "envelope": body
                            })
                        except Exception:
                            pass

        self._task = asyncio.create_task(_consumer())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._connection:
            await self._connection.close()


@pytest_asyncio.fixture
async def event_listener():
    listener = EventListener()
    await listener.start()
    yield listener
    await listener.stop()
