import asyncio
import time
import uuid
import httpx
import pytest
from tests.chaos.conftest import EMPLOYEE_URL, AUTH_URL, GATEWAY_URL, login_user_directly


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_payroll_down_during_onboarding(docker_compose, admin_token, event_listener):
    emp_uuid = uuid.uuid4().hex[:6]
    email = f"chaos.s1.{emp_uuid}@test.com"
    password = "Password123!"
    dept = f"ChaosDept-S1-{emp_uuid}"
    payload = {
        "name": f"S1 Employee {emp_uuid}",
        "email": email,
        "department": dept,
        "designation": "Software Engineer",
        "initial_password": password,
        "monthly_salary": 25000.0,
        "role": "EMPLOYEE",
    }
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Stop payroll
    docker_compose.stop("payroll")

    created_emp_id = None
    try:
        # (a) POST /employees -> 502 ONBOARDING_FAILED
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{EMPLOYEE_URL}/employees", json=payload, headers=headers)
            assert resp.status_code == 502, f"Expected 502 when payroll is down, got {resp.status_code}: {resp.text}"
            err_data = resp.json()
            assert "error" in err_data
            assert err_data["error"]["code"] == "ONBOARDING_FAILED"


        # (b) Find employee by unique department -> status ONBOARDING_FAILED
        with httpx.Client(timeout=10.0) as client:
            resp_find = client.get(f"{EMPLOYEE_URL}/employees?department={dept}", headers=headers)
            assert resp_find.status_code == 200
            items = resp_find.json()["items"]
            assert len(items) == 1, f"Expected 1 employee in dept {dept}, found {len(items)}"
            emp_rec = items[0]
            assert emp_rec["status"] == "ONBOARDING_FAILED"
            created_emp_id = emp_rec["id"]

        # (c) Logging in directly at Auth with email and password -> 401
        with httpx.Client(timeout=10.0) as client:
            resp_login = client.post(f"{AUTH_URL}/auth/login", json={"email": email, "password": password})
            assert resp_login.status_code == 401, f"Expected 401 for compensated user, got {resp_login.status_code}"

        # (d) No EmployeeOnboarded event for that employee id within 10 seconds
        await asyncio.sleep(10.0)
        onboarded_events = [
            e for e in event_listener.events
            if e["routing_key"] == "EmployeeOnboarded" and e["envelope"].get("payload", {}).get("employee_id") == created_emp_id
        ]
        assert len(onboarded_events) == 0, f"Expected 0 EmployeeOnboarded events for failed onboarding, got {len(onboarded_events)}"

        # (e) Gateway call GET /payslips/{created_emp_id} -> 502 UPSTREAM_UNAVAILABLE
        with httpx.Client(timeout=10.0) as client:
            resp_gw = client.get(f"{GATEWAY_URL}/payslips/{created_emp_id}", headers=headers)
            assert resp_gw.status_code == 502, f"Expected 502 from gateway, got {resp_gw.status_code}"
            assert resp_gw.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"

    finally:
        # (f) Start payroll, wait healthy
        docker_compose.start("payroll")
        docker_compose.wait_healthy("payroll", timeout=60.0)

        # (g) Poll onboarding of a NEW employee until 201 ACTIVE (bounded by 90s)
        t0 = time.time()
        timeout_boundary = 90.0
        success = False
        new_email = f"chaos.s1.recovery.{uuid.uuid4().hex[:6]}@test.com"
        new_payload = {
            "name": f"S1 Recovery Employee",
            "email": new_email,
            "department": f"ChaosDept-S1-Rec",
            "designation": "Engineer",
            "initial_password": "Password123!",
            "monthly_salary": 25000.0,
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
        print(f"\n[S1 Recovery Metric] Payroll healthy to first successful onboarding: {rec_time:.2f} seconds")
        assert success, f"Onboarding failed to recover within {timeout_boundary}s after Payroll became healthy"
