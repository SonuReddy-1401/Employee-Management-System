import httpx
import pytest
from tests.chaos.conftest import LEAVE_URL, login_user_directly


@pytest.mark.chaos
def test_redis_down_leave_creation(docker_compose, new_employee):
    emp = new_employee()
    emp_token = login_user_directly(emp["email"], emp["initial_password"])
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # 1. Stop redis
    docker_compose.stop("redis")

    try:
        # As employee, create a leave (Mon-Tue 2095-07-04 to 2095-07-05) -> 201 (fallback)
        payload1 = {
            "employee_id": emp["id"],
            "start_date": "2095-07-04",
            "end_date": "2095-07-05",
            "leave_type": "PAID",
            "reason": "Redis fallback test 1"
        }

        with httpx.Client(timeout=10.0) as client:
            resp_leave1 = client.post(f"{LEAVE_URL}/leaves", json=payload1, headers=emp_headers)
            assert resp_leave1.status_code == 201, f"Expected 201 leave creation when Redis is down, got {resp_leave1.status_code}: {resp_leave1.text}"

            # GET /leaves/balance/{employee_id} -> 200
            resp_bal = client.get(f"{LEAVE_URL}/leaves/balance/{emp['id']}?year=2095", headers=emp_headers)
            assert resp_bal.status_code == 200, f"Expected 200 leave balance when Redis is down, got {resp_bal.status_code}: {resp_bal.text}"

    finally:
        # Start redis, wait healthy
        docker_compose.start("redis")
        docker_compose.wait_healthy("redis", timeout=60.0)

        # Create a second non-overlapping leave (Wed-Thu 2095-07-06 to 2095-07-07) -> 201
        payload2 = {
            "employee_id": emp["id"],
            "start_date": "2095-07-06",
            "end_date": "2095-07-07",
            "leave_type": "PAID",
            "reason": "Redis recovered leave 2"
        }

        with httpx.Client(timeout=10.0) as client:
            resp_leave2 = client.post(f"{LEAVE_URL}/leaves", json=payload2, headers=emp_headers)
            assert resp_leave2.status_code == 201, f"Expected 201 leave creation after Redis recovered, got {resp_leave2.status_code}: {resp_leave2.text}"
