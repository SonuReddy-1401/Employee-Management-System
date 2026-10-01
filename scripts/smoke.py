import os
import sys
import time
import uuid
import httpx
from dotenv import load_dotenv

load_dotenv()

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
GRAFANA_ADMIN_USER = os.getenv("GRAFANA_ADMIN_USER")
GRAFANA_ADMIN_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD")

missing_env = []
if not ADMIN_EMAIL:
    missing_env.append("ADMIN_EMAIL")
if not ADMIN_PASSWORD:
    missing_env.append("ADMIN_PASSWORD")
if not GRAFANA_ADMIN_USER:
    missing_env.append("GRAFANA_ADMIN_USER")
if not GRAFANA_ADMIN_PASSWORD:
    missing_env.append("GRAFANA_ADMIN_PASSWORD")

if missing_env:
    print(f"FAIL: Missing required environment variables: {', '.join(missing_env)}")
    sys.exit(1)

failed_checks = 0


def log_result(name: str, passed: bool, details: str = ""):
    global failed_checks
    if passed:
        print(f"PASS: {name} {details}".strip())
    else:
        print(f"FAIL: {name} {details}".strip())
        failed_checks += 1


client = httpx.Client(timeout=10.0)

# Check 1: Gateway /health
try:
    resp = client.get(f"{GATEWAY_URL}/health")
    log_result("Gateway /health 200", resp.status_code == 200, f"(Status: {resp.status_code})")
except Exception as e:
    log_result("Gateway /health 200", False, f"(Error: {e})")

# Check 2: Login as seeded admin
admin_token = None
try:
    resp = client.post(
        f"{GATEWAY_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status_code == 200 and "access_token" in resp.json():
        admin_token = resp.json()["access_token"]
        log_result("Admin login", True, "(Token received)")
    else:
        log_result("Admin login", False, f"(Status: {resp.status_code}, Body: {resp.text})")
except Exception as e:
    log_result("Admin login", False, f"(Error: {e})")

# Check 3: Create employee through Gateway
employee_id = None
emp_email = f"smoke.{uuid.uuid4().hex[:6]}@ems.com"
emp_password = "SmokePassword123!"

if admin_token:
    try:
        resp = client.post(
            f"{GATEWAY_URL}/employees",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Smoke Test Employee",
                "email": emp_email,
                "department": "Engineering",
                "designation": "QA Engineer",
                "role": "EMPLOYEE",
                "initial_password": emp_password,
                "monthly_salary": 6000.0,
            },
        )
        has_cid = "x-correlation-id" in [k.lower() for k in resp.headers.keys()]
        is_active = resp.status_code == 201 and resp.json().get("status") == "ACTIVE"
        if is_active and has_cid:
            employee_id = resp.json()["id"]
            log_result("Create employee through Gateway", True, f"(ID: {employee_id}, Status: ACTIVE, X-Correlation-ID present)")
        else:
            log_result("Create employee through Gateway", False, f"(Status: {resp.status_code}, Body: {resp.text}, Correlation-ID: {has_cid})")
    except Exception as e:
        log_result("Create employee through Gateway", False, f"(Error: {e})")
else:
    log_result("Create employee through Gateway", False, "(Skipped due to failed admin login)")

# Check 4: Login with created employee
emp_token = None
if employee_id:
    try:
        resp = client.post(
            f"{GATEWAY_URL}/auth/login",
            json={"email": emp_email, "password": emp_password},
        )
        if resp.status_code == 200 and "access_token" in resp.json():
            emp_token = resp.json()["access_token"]
            log_result("Login with created employee", True, "(Token received)")
        else:
            log_result("Login with created employee", False, f"(Status: {resp.status_code}, Body: {resp.text})")
    except Exception as e:
        log_result("Login with created employee", False, f"(Error: {e})")
else:
    log_result("Login with created employee", False, "(Skipped due to employee creation failure)")

# Check 5: GET /employees/{id} returns ACTIVE
if employee_id and emp_token:
    try:
        resp = client.get(
            f"{GATEWAY_URL}/employees/{employee_id}",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        is_active = resp.status_code == 200 and resp.json().get("status") == "ACTIVE"
        log_result("GET /employees/{id} returns ACTIVE", is_active, f"(Status: {resp.status_code})")
    except Exception as e:
        log_result("GET /employees/{id} returns ACTIVE", False, f"(Error: {e})")
else:
    log_result("GET /employees/{id} returns ACTIVE", False, "(Skipped)")

# Check 6: POST /internal/users through Gateway returns 404
try:
    resp = client.post(f"{GATEWAY_URL}/internal/users", json={"email": "test@internal.com"})
    log_result("POST /internal/* returns 404", resp.status_code == 404, f"(Status: {resp.status_code})")
except Exception as e:
    log_result("POST /internal/* returns 404", False, f"(Error: {e})")

# Check 7: GET /employees without token returns 401
try:
    resp = client.get(f"{GATEWAY_URL}/employees")
    log_result("GET /employees without token returns 401", resp.status_code == 401, f"(Status: {resp.status_code})")
except Exception as e:
    log_result("GET /employees without token returns 401", False, f"(Error: {e})")

# Check 8: Prometheus targets up (wait up to 60s)
prom_ok = False
start_time = time.time()
print("Waiting for Prometheus targets to report health 'up'...")
while time.time() - start_time < 60:
    try:
        resp = client.get(f"{PROMETHEUS_URL}/api/v1/targets")
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            active_targets = data.get("activeTargets", [])
            if active_targets:
                all_up = all(t.get("health") == "up" for t in active_targets)
                if all_up:
                    prom_ok = True
                    break
    except Exception:
        pass
    time.sleep(3)

log_result("Prometheus targets up", prom_ok, f"(Checked active targets within {int(time.time() - start_time)}s)")

# Check 9: Grafana dashboard titled 'EMS System Overview'
grafana_ok = False
try:
    resp = client.get(
        f"{GRAFANA_URL}/api/search",
        auth=(GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD),
    )
    if resp.status_code == 200:
        dashboards = resp.json()
        grafana_ok = any(d.get("title") == "EMS System Overview" for d in dashboards)
    log_result("Grafana dashboard 'EMS System Overview' found", grafana_ok, f"(Status: {resp.status_code})")
except Exception as e:
    log_result("Grafana dashboard 'EMS System Overview' found", False, f"(Error: {e})")

client.close()

if failed_checks > 0:
    print(f"\nSmoke test finished with {failed_checks} failure(s).")
    sys.exit(1)
else:
    print("\nAll smoke tests passed successfully!")
    sys.exit(0)
