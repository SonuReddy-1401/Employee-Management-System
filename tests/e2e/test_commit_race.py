import os
import uuid
from datetime import date, timedelta
import httpx
import pytest

from tests.e2e.config import ADMIN_EMAIL, ADMIN_PASSWORD

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8001")
EMPLOYEE_URL = os.getenv("EMPLOYEE_URL", "http://localhost:8002")
LEAVE_URL = os.getenv("LEAVE_URL", "http://localhost:8003")
PAYROLL_URL = os.getenv("PAYROLL_URL", "http://localhost:8004")


def get_admin_token() -> str:
    with httpx.Client() as client:
        resp = client.post(f"{AUTH_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if resp.status_code != 200:
            raise RuntimeError(f"Admin login failed: {resp.status_code} {resp.text}")
        return resp.json()["access_token"]




def unique_email(prefix: str = "race") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:6]}@race.test.com"


def create_active_employee(admin_headers: dict, name: str, salary: float = 20000.0) -> dict:
    with httpx.Client() as client:
        resp = client.post(
            f"{EMPLOYEE_URL}/employees",
            json={
                "name": name,
                "email": unique_email(),
                "department": "Engineering",
                "designation": "Developer",
                "initial_password": "Password123!",
                "monthly_salary": salary,
                "role": "EMPLOYEE",
            },
            headers=admin_headers,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Create employee failed: {resp.status_code} {resp.text}")
        emp = resp.json()
        emp["initial_password"] = "Password123!"
        return emp


def test_race_scenarios():
    token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {token}"}

    # Setup 1 manager and 1 employee for leave tests
    mgr = create_active_employee(admin_headers, "Race Manager")
    # Update manager role in Auth if needed, or create via admin headers
    with httpx.Client() as client:
        # Get manager token
        mgr_login = client.post(f"{AUTH_URL}/auth/login", json={"email": mgr["email"], "password": "Password123!"})
        mgr_token = mgr_login.json()["access_token"]
        mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # --- Scenario (a) & (b): Leave Approve & Leave Cancel ---
    failures_a = 0
    first_fail_a = None
    failures_b = 0
    first_fail_b = None

    # Base date starting next year
    base_monday = date(2028, 1, 3)

    for i in range(30):
        # Create fresh employee for each iteration
        emp = create_active_employee(admin_headers, f"Leave Emp {i}")
        emp_headers = {"Authorization": f"Bearer {get_admin_token()}"} # Use admin or login as employee

        start_dt = base_monday + timedelta(weeks=i)
        end_dt = start_dt

        with httpx.Client() as client:
            req_res = client.post(
                f"{LEAVE_URL}/leaves",
                json={
                    "employee_id": emp["id"],
                    "start_date": start_dt.isoformat(),
                    "end_date": end_dt.isoformat(),
                    "leave_type": "UNPAID",
                    "reason": "Race testing",
                },
                headers=emp_headers,
            )
            if req_res.status_code != 201:
                failures_a += 1
                if not first_fail_a:
                    first_fail_a = f"POST /leaves status {req_res.status_code}: {req_res.text}"
                continue

            leave_id = req_res.json()["id"]

            # (a) Immediately approve (using admin headers)
            app_res = client.post(f"{LEAVE_URL}/leaves/{leave_id}/approve", headers=admin_headers)
            if app_res.status_code != 200:
                failures_a += 1
                if not first_fail_a:
                    first_fail_a = f"POST /leaves/{leave_id}/approve status {app_res.status_code}: {app_res.text}"

            # (b) Immediately cancel (using admin headers)
            if app_res.status_code == 200:
                cancel_res = client.post(f"{LEAVE_URL}/leaves/{leave_id}/cancel", headers=admin_headers)
                if cancel_res.status_code != 200:
                    failures_b += 1
                    if not first_fail_b:
                        first_fail_b = f"POST /leaves/{leave_id}/cancel status {cancel_res.status_code}: {cancel_res.text}"

    print(f"\nScenario (a) Leave Approve: {failures_a}/30 failures. First fail: {first_fail_a}")
    print(f"Scenario (b) Leave Cancel:  {failures_b}/30 failures. First fail: {first_fail_b}")

    # --- Scenario (c): Employee Update & Delete ---
    failures_c_update = 0
    first_fail_c_update = None
    failures_c_delete = 0
    first_fail_c_delete = None

    for i in range(30):
        emp = create_active_employee(admin_headers, f"Emp Update {i}")
        emp_id = emp["id"]
        new_designation = f"Senior Dev {i}"

        with httpx.Client() as client:
            put_res = client.put(
                f"{EMPLOYEE_URL}/employees/{emp_id}",
                json={"designation": new_designation},
                headers=admin_headers,
            )
            if put_res.status_code != 200:
                failures_c_update += 1
                if not first_fail_c_update:
                    first_fail_c_update = f"PUT /employees status {put_res.status_code}: {put_res.text}"
            else:
                # Immediately GET
                get_res = client.get(f"{EMPLOYEE_URL}/employees/{emp_id}", headers=admin_headers)
                if get_res.status_code != 200 or get_res.json().get("designation") != new_designation:
                    failures_c_update += 1
                    if not first_fail_c_update:
                        first_fail_c_update = f"GET /employees status {get_res.status_code}: {get_res.text}"

            # Immediately DELETE
            del_res = client.delete(f"{EMPLOYEE_URL}/employees/{emp_id}", headers=admin_headers)
            if del_res.status_code != 204:
                failures_c_delete += 1
                if not first_fail_c_delete:
                    first_fail_c_delete = f"DELETE /employees status {del_res.status_code}: {del_res.text}"
            else:
                # Immediately GET expect 404
                get_del_res = client.get(f"{EMPLOYEE_URL}/employees/{emp_id}", headers=admin_headers)
                if get_del_res.status_code != 404:
                    failures_c_delete += 1
                    if not first_fail_c_delete:
                        first_fail_c_delete = f"GET after DELETE status {get_del_res.status_code}: {get_del_res.text}"

    print(f"Scenario (c) Emp Update:    {failures_c_update}/30 failures. First fail: {first_fail_c_update}")
    print(f"Scenario (c) Emp Delete:    {failures_c_delete}/30 failures. First fail: {first_fail_c_delete}")

    # --- Scenario (d): Auth Login After Saga ---
    failures_d = 0
    first_fail_d = None

    for i in range(30):
        email = unique_email(f"saga{i}")
        with httpx.Client() as client:
            create_res = client.post(
                f"{EMPLOYEE_URL}/employees",
                json={
                    "name": f"Saga User {i}",
                    "email": email,
                    "department": "IT",
                    "designation": "Dev",
                    "initial_password": "Password123!",
                    "monthly_salary": 15000.0,
                    "role": "EMPLOYEE",
                },
                headers=admin_headers,
            )
            if create_res.status_code != 201:
                failures_d += 1
                if not first_fail_d:
                    first_fail_d = f"POST /employees status {create_res.status_code}: {create_res.text}"
            else:
                # Immediately login
                login_res = client.post(f"{AUTH_URL}/auth/login", json={"email": email, "password": "Password123!"})
                if login_res.status_code != 200:
                    failures_d += 1
                    if not first_fail_d:
                        first_fail_d = f"POST /auth/login status {login_res.status_code}: {login_res.text}"

    print(f"Scenario (d) Auth Login:   {failures_d}/30 failures. First fail: {first_fail_d}")

    # --- Scenario (e): Payroll Run & Get Payslips ---
    failures_e = 0
    first_fail_e = None

    payroll_emp = create_active_employee(admin_headers, "Payroll Emp")
    payroll_emp_id = payroll_emp["id"]

    for i in range(30):
        # Month format YYYY-MM
        year = 2040 + (i // 12)
        month_num = (i % 12) + 1
        month_str = f"{year}-{month_num:02d}"

        with httpx.Client() as client:
            run_res = client.post(f"{PAYROLL_URL}/payroll/run?month={month_str}", headers=admin_headers)
            if run_res.status_code != 200:
                failures_e += 1
                if not first_fail_e:
                    first_fail_e = f"POST /payroll/run status {run_res.status_code}: {run_res.text}"
            else:
                # Immediately GET /payslips/{payroll_emp_id}
                slips_res = client.get(f"{PAYROLL_URL}/payslips/{payroll_emp_id}", headers=admin_headers)
                if slips_res.status_code != 200:
                    failures_e += 1
                    if not first_fail_e:
                        first_fail_e = f"GET /payslips status {slips_res.status_code}: {slips_res.text}"
                else:
                    slips = slips_res.json()
                    has_month = any(s.get("month") == month_str for s in slips)
                    if not has_month:
                        failures_e += 1
                        if not first_fail_e:
                            first_fail_e = f"Payslip for {month_str} missing in list: {slips}"

    print(f"Scenario (e) Payroll Run:  {failures_e}/30 failures. First fail: {first_fail_e}")
