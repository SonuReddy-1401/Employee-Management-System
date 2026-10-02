import uuid
from datetime import date, timedelta
import httpx
import pytest
from tests.contract.conftest import GATEWAY_URL, login_user_directly
from tests.contract.schema_helper import validate_schema


def count_business_days(start_str: str, end_str: str) -> int:
    cur = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    days = 0
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


@pytest.mark.asyncio
async def test_employee_onboarded_event_contract(event_listener, admin_token):
    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Correlation-ID": correlation_id
    }
    email = f"eventonboard.{uuid.uuid4().hex[:6]}@contract.test.com"
    payload = {
        "name": "Event Onboard Test",
        "email": email,
        "department": "Engineering",
        "designation": "Engineer",
        "initial_password": "Password123!",
        "monthly_salary": 20000.0,
        "role": "EMPLOYEE"
    }

    with httpx.Client() as client:
        resp = client.post(f"{GATEWAY_URL}/employees", json=payload, headers=headers)
        assert resp.status_code == 201
        emp_id = resp.json()["id"]

    event_msg = await event_listener.wait_for(
        lambda ev: ev["routing_key"] == "EmployeeOnboarded" and ev["envelope"].get("correlation_id") == correlation_id,
        timeout=30.0
    )

    routing_key = event_msg["routing_key"]
    envelope = event_msg["envelope"]

    assert routing_key == "EmployeeOnboarded"
    validate_schema(envelope, "event-envelope.json")
    validate_schema(envelope["payload"], "EmployeeOnboarded.json")
    assert envelope["correlation_id"] == correlation_id
    assert envelope["payload"]["employee_id"] == emp_id


@pytest.mark.asyncio
async def test_leave_events_contract_lifecycle(event_listener, new_employee, admin_token):
    # Setup manager and employee
    manager = new_employee(role="MANAGER")
    mgr_token = login_user_directly(manager["email"], manager["initial_password"])
    mgr_headers_base = {"Authorization": f"Bearer {mgr_token}"}

    employee = new_employee(role="EMPLOYEE", manager_id=manager["id"])
    emp_token = login_user_directly(employee["email"], employee["initial_password"])
    emp_headers_base = {"Authorization": f"Bearer {emp_token}"}

    today = date.today()

    # --- 1. LeaveRequested ---
    req_correlation_id = str(uuid.uuid4())
    emp_headers_req = {**emp_headers_base, "X-Correlation-ID": req_correlation_id}
    start_1 = (today + timedelta(days=10)).isoformat()
    end_1 = (today + timedelta(days=14)).isoformat()
    expected_days_1 = count_business_days(start_1, end_1)

    leave_payload_1 = {
        "employee_id": employee["id"],
        "start_date": start_1,
        "end_date": end_1,
        "leave_type": "PAID",
        "reason": "Event contract test leave 1"
    }

    with httpx.Client() as client:
        resp1 = client.post(f"{GATEWAY_URL}/leaves", json=leave_payload_1, headers=emp_headers_req)
        assert resp1.status_code == 201
        leave_id_1 = resp1.json()["id"]

    msg_req = await event_listener.wait_for(
        lambda ev: ev["routing_key"] == "LeaveRequested" and ev["envelope"].get("correlation_id") == req_correlation_id,
        timeout=30.0
    )
    env_req = msg_req["envelope"]
    assert msg_req["routing_key"] == "LeaveRequested"
    validate_schema(env_req, "event-envelope.json")
    validate_schema(env_req["payload"], "LeaveRequested.json")
    assert env_req["correlation_id"] == req_correlation_id
    assert env_req["payload"]["days"] == expected_days_1

    # --- 2. LeaveApproved ---
    app_correlation_id = str(uuid.uuid4())
    mgr_headers_app = {**mgr_headers_base, "X-Correlation-ID": app_correlation_id}

    with httpx.Client() as client:
        resp_app = client.post(f"{GATEWAY_URL}/leaves/{leave_id_1}/approve", headers=mgr_headers_app)
        assert resp_app.status_code == 200

    msg_app = await event_listener.wait_for(
        lambda ev: ev["routing_key"] == "LeaveApproved" and ev["envelope"].get("correlation_id") == app_correlation_id,
        timeout=30.0
    )
    env_app = msg_app["envelope"]
    assert msg_app["routing_key"] == "LeaveApproved"
    validate_schema(env_app, "event-envelope.json")
    validate_schema(env_app["payload"], "LeaveApproved.json")
    assert env_app["correlation_id"] == app_correlation_id
    assert env_app["payload"]["days"] == expected_days_1

    # --- 3. LeaveCancelled ---
    can_correlation_id = str(uuid.uuid4())
    emp_headers_can = {**emp_headers_base, "X-Correlation-ID": can_correlation_id}

    with httpx.Client() as client:
        resp_can = client.post(f"{GATEWAY_URL}/leaves/{leave_id_1}/cancel", headers=emp_headers_can)
        assert resp_can.status_code == 200

    msg_can = await event_listener.wait_for(
        lambda ev: ev["routing_key"] == "LeaveCancelled" and ev["envelope"].get("correlation_id") == can_correlation_id,
        timeout=30.0
    )
    env_can = msg_can["envelope"]
    assert msg_can["routing_key"] == "LeaveCancelled"
    validate_schema(env_can, "event-envelope.json")
    validate_schema(env_can["payload"], "LeaveCancelled.json")
    assert env_can["correlation_id"] == can_correlation_id
    assert env_can["payload"]["days"] == expected_days_1

    # --- 4. LeaveRejected ---
    start_2 = (today + timedelta(days=20)).isoformat()
    end_2 = (today + timedelta(days=22)).isoformat()
    expected_days_2 = count_business_days(start_2, end_2)
    leave_payload_2 = {
        "employee_id": employee["id"],
        "start_date": start_2,
        "end_date": end_2,
        "leave_type": "UNPAID",
        "reason": "Event contract test leave 2"
    }
    with httpx.Client() as client:
        resp2 = client.post(f"{GATEWAY_URL}/leaves", json=leave_payload_2, headers=emp_headers_base)
        assert resp2.status_code == 201
        leave_id_2 = resp2.json()["id"]

    rej_correlation_id = str(uuid.uuid4())
    mgr_headers_rej = {**mgr_headers_base, "X-Correlation-ID": rej_correlation_id}

    with httpx.Client() as client:
        resp_rej = client.post(f"{GATEWAY_URL}/leaves/{leave_id_2}/reject", headers=mgr_headers_rej)
        assert resp_rej.status_code == 200

    msg_rej = await event_listener.wait_for(
        lambda ev: ev["routing_key"] == "LeaveRejected" and ev["envelope"].get("correlation_id") == rej_correlation_id,
        timeout=30.0
    )
    env_rej = msg_rej["envelope"]
    assert msg_rej["routing_key"] == "LeaveRejected"
    validate_schema(env_rej, "event-envelope.json")
    validate_schema(env_rej["payload"], "LeaveRejected.json")
    assert env_rej["correlation_id"] == rej_correlation_id
    assert env_rej["payload"]["days"] == expected_days_2

    # Check unique event_ids across captured events
    captured_event_ids = [
        env_req["event_id"], env_app["event_id"], env_can["event_id"], env_rej["event_id"]
    ]
    assert len(set(captured_event_ids)) == len(captured_event_ids)
