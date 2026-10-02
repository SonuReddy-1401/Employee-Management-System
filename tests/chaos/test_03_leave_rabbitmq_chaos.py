import asyncio
import subprocess
import time
import uuid
import httpx
import pytest
from tests.chaos.conftest import LEAVE_URL, NOTIFICATION_URL, PAYROLL_URL, login_user_directly, REPO_ROOT


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_rabbitmq_down_during_leave_approval(docker_compose, new_employee, admin_token):
    # 1. Create manager and employee
    mgr = new_employee(role="MANAGER")
    emp = new_employee(role="EMPLOYEE", manager_id=mgr["id"])

    emp_token = login_user_directly(emp["email"], emp["initial_password"])
    mgr_token = login_user_directly(mgr["email"], mgr["initial_password"])

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Create an UNPAID leave in a unique far-future month (Mon-Fri 5 days)
    # 2097-05-06 (Mon) to 2097-05-10 (Fri)
    month_str = "2097-05"
    start_date = "2097-05-06"
    end_date = "2097-05-10"

    leave_payload = {
        "employee_id": emp["id"],
        "start_date": start_date,
        "end_date": end_date,
        "leave_type": "UNPAID",
        "reason": "RabbitMQ Chaos test leave"
    }

    with httpx.Client(timeout=10.0) as client:
        resp_create = client.post(f"{LEAVE_URL}/leaves", json=leave_payload, headers=emp_headers)
        assert resp_create.status_code == 201, f"Failed to create leave: {resp_create.status_code} {resp_create.text}"
        leave_id = resp_create.json()["id"]

    # 3. Stop rabbitmq
    docker_compose.stop("rabbitmq")

    try:
        # 4. Manager approves leave -> 200 (outbox absorbs outage)
        with httpx.Client(timeout=10.0) as client:
            resp_app = client.post(f"{LEAVE_URL}/leaves/{leave_id}/approve", headers=mgr_headers)
            assert resp_app.status_code == 200, f"Expected 200 on leave approve during RabbitMQ outage, got {resp_app.status_code}: {resp_app.text}"
            assert resp_app.json()["status"] == "APPROVED"

    except Exception as exc:
        logs_res = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "logs", "--tail", "50", "leave", "payroll", "notification"],
            cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        raise AssertionError(f"Leave approval failed while RabbitMQ down: {exc}\n\nLogs:\n{logs_res.stdout}\n{logs_res.stderr}")

    finally:
        # 5. Start rabbitmq, wait healthy
        docker_compose.start("rabbitmq")
        docker_compose.wait_healthy("rabbitmq", timeout=60.0)

        # 6. Bounded wait (93 seconds)
        t0 = time.time()
        timeout_boundary = 93.0
        notif_found = False
        measured_time = None

        while time.time() - t0 < timeout_boundary:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp_notif = client.get(f"{NOTIFICATION_URL}/notifications/{emp['id']}", headers=emp_headers)
                    if resp_notif.status_code == 200:
                        notifs = resp_notif.json()
                        leave_app_notifs = [
                            n for n in notifs
                            if n.get("event_type") == "LeaveApproved" and start_date in n.get("message", "")
                        ]

                        if len(leave_app_notifs) == 1:
                            notif_found = True
                            if measured_time is None:
                                measured_time = time.time() - t0
                            break
            except Exception:
                pass
            await asyncio.sleep(1.0)

        if not notif_found:
            logs_res = subprocess.run(
                ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "logs", "--tail", "50", "leave", "payroll", "notification"],
                cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            pytest.fail(f"LeaveApproved notification for leave {leave_id} did not arrive within {timeout_boundary}s after RabbitMQ recovered.\n\nLogs:\n{logs_res.stdout}\n{logs_res.stderr}")

        print(f"\n[S3 Recovery Metric] RabbitMQ healthy to LeaveApproved notification: {measured_time:.2f} seconds")

        # Check payroll calculation
        with httpx.Client(timeout=30.0) as client:
            resp_run = client.post(f"{PAYROLL_URL}/payroll/run?month={month_str}", headers=admin_headers)
            assert resp_run.status_code == 200

            resp_slips = client.get(f"{PAYROLL_URL}/payslips/{emp['id']}", headers=admin_headers)
            assert resp_slips.status_code == 200
            slips = resp_slips.json()
            assert len(slips) > 0
            target_slip = [s for s in slips if s["month"] == month_str][0]
            assert target_slip["unpaid_leave_days"] == 5
            gross = float(target_slip["gross_salary"])
            deduction = float(target_slip["deduction"])
            assert deduction > 0.0, f"Expected deduction > 0, got {deduction}"
