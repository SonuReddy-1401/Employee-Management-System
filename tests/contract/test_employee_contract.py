import uuid
import httpx
import pytest
from tests.contract.conftest import EMPLOYEE_URL
from tests.contract.schema_helper import validate_schema


def test_employee_contract_lifecycle(new_employee, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create employee (handled by new_employee fixture) -> matches employee schema
    emp = new_employee()
    validate_schema(emp, "employee.json")
    emp_id = emp["id"]

    with httpx.Client() as client:
        # 2. GET /employees/{id} -> 200 matches employee schema
        resp_get = client.get(f"{EMPLOYEE_URL}/employees/{emp_id}", headers=headers)
        assert resp_get.status_code == 200
        validate_schema(resp_get.json(), "employee.json")

        # 3. GET /employees -> 200 matches employee-list schema
        resp_list = client.get(f"{EMPLOYEE_URL}/employees?page=1&page_size=10", headers=headers)
        assert resp_list.status_code == 200
        validate_schema(resp_list.json(), "employee-list.json")

        # 4. PUT /employees/{id} -> 200 matches employee schema
        update_payload = {"designation": "Senior Software Engineer"}
        resp_put = client.put(f"{EMPLOYEE_URL}/employees/{emp_id}", json=update_payload, headers=headers)
        assert resp_put.status_code == 200
        validate_schema(resp_put.json(), "employee.json")

        # 5. DELETE /employees/{id} -> 204
        resp_del = client.delete(f"{EMPLOYEE_URL}/employees/{emp_id}", headers=headers)
        assert resp_del.status_code == 204

        # 6. GET /employees/{id} after delete -> 404 matches error schema
        resp_404 = client.get(f"{EMPLOYEE_URL}/employees/{emp_id}", headers=headers)
        assert resp_404.status_code == 404
        validate_schema(resp_404.json(), "error-response.json")


def test_employee_invalid_manager_id(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    fake_id = str(uuid.uuid4())
    payload = {
        "name": "Invalid Manager Test",
        "email": f"badman.{uuid.uuid4().hex[:6]}@contract.test.com",
        "department": "Engineering",
        "designation": "Developer",
        "initial_password": "Password123!",
        "monthly_salary": 20000.0,
        "manager_id": fake_id,
        "role": "EMPLOYEE"
    }
    with httpx.Client() as client:
        resp = client.post(f"{EMPLOYEE_URL}/employees", json=payload, headers=headers)
        assert resp.status_code == 422
        validate_schema(resp.json(), "error-response.json")
