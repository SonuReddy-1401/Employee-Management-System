import asyncio
import time
import uuid
import httpx
import pytest
from tests.chaos.conftest import EMPLOYEE_URL, LEAVE_URL, NOTIFICATION_URL, login_user_directly


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_notification_down_event_durability(docker_compose, admin_token):
    # 1. Stop notification service
    docker_compose.stop("notification")

    emp_id = None
    leave_id = None
    try:
        # Onboard an employee (triggers EmployeeOnboarded)
        emp_uuid = uuid.uuid4().hex[:6]
        email = f"chaos.s4.{emp_uuid}@test.com"
        password = "Password123!"
        dept = f"ChaosDept-S4-{emp_uuid}"
        payload = {
            "name": f"S4 Employee {emp_uuid}",
            "email": email,
            "department": dept,
            "designation": "DevOps Engineer",
            "initial_password": password,
            "monthly_salary": 32000.0,
            "role": "EMPLOYEE",
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        with httpx.Client(timeout=10.0) as client:
            resp_emp = client.post(f"{EMPLOYEE_URL}/employees", json=payload, headers=headers)
            assert resp_emp.status_code == 201
            emp = resp_emp.json()
            emp_id = emp["id"]

        emp_token = login_user_directly(email, password)
        emp_headers = {"Authorization": f"Bearer {emp_token}"}

        # Create a leave (triggers LeaveRequested)
        # 2096-06-04 (Mon) to 2096-06-05 (Tue)
        leave_payload = {
            "employee_id": emp_id,
            "start_date": "2096-06-04",
            "end_date": "2096-06-05",
            "leave_type": "UNPAID",
            "reason": "Notification durability test"
        }
        with httpx.Client(timeout=10.0) as client:
            resp_leave = client.post(f"{LEAVE_URL}/leaves", json=leave_payload, headers=emp_headers)
            assert resp_leave.status_code == 201
            leave_id = resp_leave.json()["id"]

    finally:
        # Start notification, wait healthy
        docker_compose.start("notification")
        docker_compose.wait_healthy("notification", timeout=60.0)

        # Bounded wait (60s)
        t0 = time.time()
        timeout_boundary = 60.0
        success = False
        measured_time = None

        while time.time() - t0 < timeout_boundary:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp_notif = client.get(f"{NOTIFICATION_URL}/notifications/{emp_id}", headers=headers)
                    if resp_notif.status_code == 200:

                        notifs = resp_notif.json()
                        onboard_notifs = [n for n in notifs if n.get("event_type") == "EmployeeOnboarded"]
                        leave_notifs = [n for n in notifs if n.get("event_type") == "LeaveRequested"]

                        if len(onboard_notifs) == 1 and len(leave_notifs) == 1:
                            success = True
                            if measured_time is None:
                                measured_time = time.time() - t0
                            break
            except Exception:
                pass
            await asyncio.sleep(1.0)

        assert success, f"Failed to deliver notifications without duplication after Notification service recovery within {timeout_boundary}s"
        print(f"\n[S4 Recovery Metric] Notification healthy to notifications delivery: {measured_time:.2f} seconds")
