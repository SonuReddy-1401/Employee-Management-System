import uuid
import httpx
import pytest
from tests.contract.conftest import PAYROLL_URL, login_user_directly
from tests.contract.schema_helper import validate_schema


def test_payroll_internal_profile_lifecycle():
    emp_id = str(uuid.uuid4())
    payload = {"employee_id": emp_id, "monthly_salary": 30000.0}

    with httpx.Client() as client:
        # 1. POST /internal/profiles -> 201
        resp = client.post(f"{PAYROLL_URL}/internal/profiles", json=payload)
        assert resp.status_code == 201
        validate_schema(resp.json(), "payroll-profile.json")

        # 2. Identical repeat -> 200
        resp_repeat = client.post(f"{PAYROLL_URL}/internal/profiles", json=payload)
        assert resp_repeat.status_code == 200
        validate_schema(resp_repeat.json(), "payroll-profile.json")

        # 3. Different salary -> 409
        payload_diff = {"employee_id": emp_id, "monthly_salary": 35000.0}
        resp_diff = client.post(f"{PAYROLL_URL}/internal/profiles", json=payload_diff)
        assert resp_diff.status_code == 409
        validate_schema(resp_diff.json(), "error-response.json")


def test_payroll_internal_profile_repeated_delete():
    emp_id = str(uuid.uuid4())
    with httpx.Client() as client:
        resp1 = client.delete(f"{PAYROLL_URL}/internal/profiles/{emp_id}")
        assert resp1.status_code == 204
        assert resp1.text == ""

        resp2 = client.delete(f"{PAYROLL_URL}/internal/profiles/{emp_id}")
        assert resp2.status_code == 204
        assert resp2.text == ""


def test_payroll_run_and_payslips(new_employee, admin_token):
    emp = new_employee()
    emp_id = emp["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}
    far_future_month = f"2099-{uuid.uuid4().int % 12 + 1:02d}"

    with httpx.Client(timeout=30.0) as client:
        resp_run = client.post(f"{PAYROLL_URL}/payroll/run?month={far_future_month}", headers=headers)
        assert resp_run.status_code == 200
        validate_schema(resp_run.json(), "payroll-run-result.json")

        resp_slips = client.get(f"{PAYROLL_URL}/payslips/{emp_id}", headers=headers)
        assert resp_slips.status_code == 200
        slips = resp_slips.json()
        assert isinstance(slips, list)
        if slips:
            validate_schema(slips[0], "payslip.json")


def test_payroll_run_malformed_month(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    with httpx.Client() as client:
        resp = client.post(f"{PAYROLL_URL}/payroll/run?month=invalid-month-format", headers=headers)
        assert resp.status_code == 422
        validate_schema(resp.json(), "error-response.json")


def test_payslips_forbidden_for_other_employee(new_employee):
    emp1 = new_employee()
    emp2 = new_employee()
    token1 = login_user_directly(emp1["email"], emp1["initial_password"])
    headers1 = {"Authorization": f"Bearer {token1}"}

    with httpx.Client() as client:
        resp = client.get(f"{PAYROLL_URL}/payslips/{emp2['id']}", headers=headers1)
        assert resp.status_code == 403
        validate_schema(resp.json(), "error-response.json")


def test_payroll_run_unauthorized():
    with httpx.Client() as client:
        resp = client.post(f"{PAYROLL_URL}/payroll/run?month=2099-01")
        assert resp.status_code == 401
        validate_schema(resp.json(), "error-response.json")
