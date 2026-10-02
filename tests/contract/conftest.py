import asyncio
import os
import uuid
import json
import httpx
import pytest
import aio_pika
from dotenv import load_dotenv

load_dotenv()

AUTH_URL = os.getenv("CONTRACT_AUTH_URL", "http://localhost:8001")
EMPLOYEE_URL = os.getenv("CONTRACT_EMPLOYEE_URL", "http://localhost:8002")
LEAVE_URL = os.getenv("CONTRACT_LEAVE_URL", "http://localhost:8003")
PAYROLL_URL = os.getenv("CONTRACT_PAYROLL_URL", "http://localhost:8004")
NOTIFICATION_URL = os.getenv("CONTRACT_NOTIFICATION_URL", "http://localhost:8005")
GATEWAY_URL = os.getenv("CONTRACT_GATEWAY_URL", "http://localhost:8000")

RABBITMQ_HOST = os.getenv("CONTRACT_RABBITMQ_HOST", "localhost")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
RABBITMQ_USER = os.getenv("RABBITMQ_MGMT_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_MGMT_PASSWORD")

missing = []
if not ADMIN_EMAIL:
    missing.append("ADMIN_EMAIL")
if not ADMIN_PASSWORD:
    missing.append("ADMIN_PASSWORD")
if not RABBITMQ_USER:
    missing.append("RABBITMQ_MGMT_USER")
if not RABBITMQ_PASS:
    missing.append("RABBITMQ_MGMT_PASSWORD")

if missing:
    raise RuntimeError(
        f"Missing required environment variables for contract tests: {', '.join(missing)}. "
        f"Ensure .env file exists and contains these credentials."
    )


@pytest.fixture(scope="session", autouse=True)
def check_stack_health():
    services = {
        "Gateway": GATEWAY_URL,
        "Auth": AUTH_URL,
        "Employee": EMPLOYEE_URL,
        "Leave": LEAVE_URL,
        "Payroll": PAYROLL_URL,
        "Notification": NOTIFICATION_URL,
    }
    with httpx.Client(timeout=5.0) as client:
        for name, url in services.items():
            try:
                resp = client.get(f"{url}/health")
                if resp.status_code != 200:
                    pytest.fail(f"Start the stack: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait (Service {name} returned status {resp.status_code})")
            except Exception as exc:
                pytest.fail(f"Start the stack: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait (Service {name} at {url} unreachable: {exc})")


def login_user_directly(email: str, password: str) -> str:
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(f"{AUTH_URL}/auth/login", json={"email": email, "password": password})
        if resp.status_code != 200:
            raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
        return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(check_stack_health) -> str:
    return login_user_directly(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def new_employee(admin_token):
    created_employees = []

    def _create_employee(role: str = "EMPLOYEE", manager_id: str | None = None) -> dict:
        email = f"contract.{uuid.uuid4().hex[:6]}@contract.test.com"
        password = "Password123!"
        payload = {
            "name": f"Contract Test {uuid.uuid4().hex[:4]}",
            "email": email,
            "department": "Engineering",
            "designation": "Software Engineer",
            "initial_password": password,
            "monthly_salary": 25000.0,
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
            created_employees.append(emp_data)
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
        queue_name = f"contract.queue.{uuid.uuid4().hex}"
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
                        except Exception as exc:
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

    async def wait_for(self, predicate, timeout: float = 30.0):
        start_time = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - start_time) < timeout:
            for ev in self.events:
                if predicate(ev):
                    return ev
            await asyncio.sleep(1.0)
        raise TimeoutError(f"Event matching predicate not received within {timeout}s. Events received: {self.events}")


import pytest_asyncio

@pytest_asyncio.fixture
async def event_listener():
    listener = EventListener()
    await listener.start()
    yield listener
    await listener.stop()

