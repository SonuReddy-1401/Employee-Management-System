import os
import sys
from dotenv import load_dotenv

load_dotenv()

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
RABBITMQ_MGMT_URL = os.getenv("RABBITMQ_MGMT_URL", "http://localhost:15672")
E2E_WAIT_TIMEOUT_SECONDS = int(os.getenv("E2E_WAIT_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
RABBITMQ_MGMT_USER = os.getenv("RABBITMQ_MGMT_USER")
RABBITMQ_MGMT_PASSWORD = os.getenv("RABBITMQ_MGMT_PASSWORD")

missing_vars = []
if not ADMIN_EMAIL:
    missing_vars.append("ADMIN_EMAIL")
if not ADMIN_PASSWORD:
    missing_vars.append("ADMIN_PASSWORD")
if not RABBITMQ_MGMT_USER:
    missing_vars.append("RABBITMQ_MGMT_USER")
if not RABBITMQ_MGMT_PASSWORD:
    missing_vars.append("RABBITMQ_MGMT_PASSWORD")

if missing_vars:
    raise RuntimeError(
        f"E2E configuration missing required environment variables: {', '.join(missing_vars)}. "
        f"Ensure .env file exists and contains these credentials."
    )
