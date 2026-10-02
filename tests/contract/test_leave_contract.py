import uuid
from datetime import date, timedelta
import httpx
import pytest
from tests.contract.conftest import LEAVE_URL, login_user_directly
from tests.contract.schema_helper import validate_schema


def test_leave_contract_lifecycle(new_employee, admin_token):
    emp = new_employee()
    emp_token = login_user_directly(emp["email"], emp["initial_password"])
    emp_id = emp["id"]

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    today = date.today()
    start_date = (today + timedelta(days=10)).isoformat()
    end_date = (today + timedelta(days=12)).isoformat()

    with httpx.Client() as client:
        # 1. POST /leaves -> 201 matches leave schema
        leave_payload = {
            "employee_id": emp_id,
            "start_date": start_date,
            "end_date": end_date,
            "leave_type": "PAID",
            "reason": "Contract testing leave"
        }
        resp = client.post(f"{LEAVE_URL}/leaves", json=leave_payload, headers=emp_headers)
        assert resp.status_code == 201
        leave_data = resp.json()
        validate_schema(leave_data, "leave.json")
        leave_id = leave_data["id"]

        # 2. GET /leaves/balance/{employee_id} -> 200 matches leave-balance schema
        resp_bal = client.get(f"{LEAVE_URL}/leaves/balance/{emp_id}?year={today.year}", headers=emp_headers)
        assert resp_bal.status_code == 200
        validate_schema(resp_bal.json(), "leave-balance.json")

        # 3. POST /leaves/{id}/approve -> 200
        resp_app = client.post(f"{LEAVE_URL}/leaves/{leave_id}/approve", headers=admin_headers)
        assert resp_app.status_code == 200
        validate_schema(resp_app.json(), "leave.json")

        # 4. Invalid transition: approving an already APPROVED leave -> 409 matches error schema
        resp_inv = client.post(f"{LEAVE_URL}/leaves/{leave_id}/approve", headers=admin_headers)
        assert resp_inv.status_code == 409
        validate_schema(resp_inv.json(), "error-response.json")


def test_leave_list_envelope(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    with httpx.Client() as client:
        resp = client.get(f"{LEAVE_URL}/leaves?page=1&page_size=10", headers=headers)
        assert resp.status_code == 200
        validate_schema(resp.json(), "leave-list.json")


def test_leave_direct_reject_provider(new_employee, admin_token):
    emp = new_employee()
    emp_token = login_user_directly(emp["email"], emp["initial_password"])
    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    today = date.today()
    # Find next Monday (at least 7 days ahead)
    days_until_monday = (7 - today.weekday()) % 7 + 7
    start_dt = today + timedelta(days=days_until_monday)
    end_dt = start_dt + timedelta(days=1)  # Tuesday

    payload = {
        "employee_id": emp["id"],
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "leave_type": "UNPAID",
        "reason": "Direct reject test"
    }
    with httpx.Client() as client:
        resp_create = client.post(f"{LEAVE_URL}/leaves", json=payload, headers=emp_headers)
        assert resp_create.status_code == 201
        leave_id = resp_create.json()["id"]

        resp_rej = client.post(f"{LEAVE_URL}/leaves/{leave_id}/reject", headers=admin_headers)
        assert resp_rej.status_code == 200
        validate_schema(resp_rej.json(), "leave.json")


def test_leave_direct_cancel_provider(new_employee):
    emp = new_employee()
    emp_token = login_user_directly(emp["email"], emp["initial_password"])
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7 + 14
    start_dt = today + timedelta(days=days_until_monday)
    end_dt = start_dt + timedelta(days=1)  # Tuesday

    payload = {
        "employee_id": emp["id"],
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "leave_type": "UNPAID",
        "reason": "Direct cancel test"
    }
    with httpx.Client() as client:
        resp_create = client.post(f"{LEAVE_URL}/leaves", json=payload, headers=emp_headers)
        assert resp_create.status_code == 201
        leave_id = resp_create.json()["id"]

        resp_can = client.post(f"{LEAVE_URL}/leaves/{leave_id}/cancel", headers=emp_headers)
        assert resp_can.status_code == 200
        validate_schema(resp_can.json(), "leave.json")



def test_leave_forbidden_for_other_employee(new_employee):
    emp1 = new_employee()
    emp2 = new_employee()
    token1 = login_user_directly(emp1["email"], emp1["initial_password"])
    headers1 = {"Authorization": f"Bearer {token1}"}

    today = date.today()
    payload = {
        "employee_id": emp2["id"],
        "start_date": (today + timedelta(days=20)).isoformat(),
        "end_date": (today + timedelta(days=21)).isoformat(),
        "leave_type": "PAID",
    }
    with httpx.Client() as client:
        resp = client.post(f"{LEAVE_URL}/leaves", json=payload, headers=headers1)
        assert resp.status_code == 403
        validate_schema(resp.json(), "error-response.json")


def test_leave_balance_forbidden_for_other_employee(new_employee):
    emp1 = new_employee()
    emp2 = new_employee()
    token1 = login_user_directly(emp1["email"], emp1["initial_password"])
    headers1 = {"Authorization": f"Bearer {token1}"}

    with httpx.Client() as client:
        resp = client.get(f"{LEAVE_URL}/leaves/balance/{emp2['id']}?year=2026", headers=headers1)
        assert resp.status_code == 403
        validate_schema(resp.json(), "error-response.json")
