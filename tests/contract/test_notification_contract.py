import time
import httpx
import pytest
from tests.contract.conftest import NOTIFICATION_URL, login_user_directly
from tests.contract.schema_helper import validate_schema


def test_notification_contract_lifecycle(new_employee, admin_token):
    # Onboard employee creates EmployeeOnboarded event which produces a notification
    emp = new_employee()
    emp_id = emp["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}

    # Poll until notification arrives or timeout 15s
    start = time.time()
    notifications = []
    with httpx.Client() as client:
        while time.time() - start < 15.0:
            resp = client.get(f"{NOTIFICATION_URL}/notifications/{emp_id}", headers=headers)
            assert resp.status_code == 200
            notifications = resp.json()
            if notifications:
                break
            time.sleep(1.0)

    assert len(notifications) >= 1
    validate_schema(notifications[0], "notification-item.json")


def test_notification_forbidden_for_other_employee(new_employee):
    emp1 = new_employee()
    emp2 = new_employee()
    token1 = login_user_directly(emp1["email"], emp1["initial_password"])
    headers1 = {"Authorization": f"Bearer {token1}"}

    with httpx.Client() as client:
        resp = client.get(f"{NOTIFICATION_URL}/notifications/{emp2['id']}", headers=headers1)
        assert resp.status_code == 403
        validate_schema(resp.json(), "error-response.json")


def test_notification_unauthorized(new_employee):
    emp = new_employee()
    with httpx.Client() as client:
        resp = client.get(f"{NOTIFICATION_URL}/notifications/{emp['id']}")
        assert resp.status_code == 401
        validate_schema(resp.json(), "error-response.json")
