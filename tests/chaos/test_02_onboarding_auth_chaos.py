import asyncio
import time
import uuid
import httpx
import pytest
from tests.chaos.conftest import EMPLOYEE_URL, AUTH_URL, PAYROLL_URL


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_auth_down_during_onboarding(docker_compose, admin_token):
    emp_uuid = uuid.uuid4().hex[:6]
    email = f"chaos.s2.{emp_uuid}@test.com"
    password = "Password123!"
    dept = f"ChaosDept-S2-{emp_uuid}"
    payload = {
        "name": f"S2 Employee {emp_uuid}",
        "email": email,
        "department": dept,
        "designation": "QA Engineer",
        "initial_password": password,
        "monthly_salary": 28000.0,
        "role": "EMPLOYEE",
    }
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Stop auth
    docker_compose.stop("auth")

    created_emp_id = None
    try:
        # POST /employees -> 502 ONBOARDING_FAILED
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{EMPLOYEE_URL}/employees", json=payload, headers=headers)
            assert resp.status_code == 502, f"Expected 502 when auth is down, got {resp.status_code}: {resp.text}"
            assert resp.json()["error"]["code"] == "ONBOARDING_FAILED"


        # Search employee by department -> status ONBOARDING_FAILED
        with httpx.Client(timeout=10.0) as client:
            resp_find = client.get(f"{EMPLOYEE_URL}/employees?department={dept}", headers=headers)
            assert resp_find.status_code == 200
            items = resp_find.json()["items"]
            assert len(items) == 1
            emp_rec = items[0]
            assert emp_rec["status"] == "ONBOARDING_FAILED"
            created_emp_id = emp_rec["id"]

        # Start auth, wait healthy
        docker_compose.start("auth")
        docker_compose.wait_healthy("auth", timeout=60.0)

        # Run POST /payroll/run for a unique far-future month
        far_future_month = f"2098-{(uuid.uuid4().int % 12) + 1:02d}"
        with httpx.Client(timeout=30.0) as client:
            resp_run = client.post(f"{PAYROLL_URL}/payroll/run?month={far_future_month}", headers=headers)
            assert resp_run.status_code == 200

            # Assert GET /payslips/{created_emp_id} is an empty list (no payroll profile was left behind)
            resp_slips = client.get(f"{PAYROLL_URL}/payslips/{created_emp_id}", headers=headers)
            assert resp_slips.status_code == 200
            assert resp_slips.json() == [], f"Expected empty payslip list for failed onboarding employee, got {resp_slips.json()}"

    finally:
        # Ensure auth is started and healthy
        docker_compose.start("auth")
        docker_compose.wait_healthy("auth", timeout=60.0)

        # Poll a NEW onboarding until 201 ACTIVE (bounded by 90s)
        t0 = time.time()
        timeout_boundary = 90.0
        success = False
        new_email = f"chaos.s2.recovery.{uuid.uuid4().hex[:6]}@test.com"
        new_payload = {
            "name": f"S2 Recovery Employee",
            "email": new_email,
            "department": f"ChaosDept-S2-Rec",
            "designation": "QA Engineer",
            "initial_password": "Password123!",
            "monthly_salary": 28000.0,
            "role": "EMPLOYEE",
        }
        while time.time() - t0 < timeout_boundary:
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.post(f"{EMPLOYEE_URL}/employees", json=new_payload, headers=headers)
                    if res.status_code == 201 and res.json().get("status") == "ACTIVE":
                        success = True
                        break
            except Exception:
                pass
            await asyncio.sleep(1.0)

        rec_time = time.time() - t0
        print(f"\n[S2 Recovery Metric] Auth healthy to first successful onboarding: {rec_time:.2f} seconds")
        assert success, f"Onboarding failed to recover within {timeout_boundary}s after Auth became healthy"
