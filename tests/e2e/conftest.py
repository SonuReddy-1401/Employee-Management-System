import pytest
from tests.e2e.config import ADMIN_EMAIL, ADMIN_PASSWORD
from tests.e2e.helpers import E2EClient, unique_email


@pytest.fixture(scope="session")
def admin_client():
    client = E2EClient()
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    yield client
    client.close()


@pytest.fixture(scope="session")
def employee_factory(admin_client):
    created_employees = []

    def _create_employee(
        name: str = "E2E Employee",
        email: str | None = None,
        department: str = "Engineering",
        designation: str = "Software Engineer",
        role: str = "EMPLOYEE",
        initial_password: str = "Password123!",
        monthly_salary: float = 5000.0,
        manager_id: str | None = None,
    ) -> dict:
        if email is None:
            email = unique_email()

        payload = {
            "name": name,
            "email": email,
            "department": department,
            "designation": designation,
            "role": role,
            "initial_password": initial_password,
            "monthly_salary": monthly_salary,
        }
        if manager_id:
            payload["manager_id"] = manager_id

        resp = admin_client.post("/employees", json=payload)
        assert resp.status_code == 201, f"Failed to create employee {email}: {resp.status_code} {resp.text}"
        data = resp.json()

        emp_info = {
            "id": data["id"],
            "name": data["name"],
            "email": email,
            "password": initial_password,
            "role": role,
            "monthly_salary": monthly_salary,
            "manager_id": data.get("manager_id"),
        }
        created_employees.append(emp_info)
        return emp_info

    yield _create_employee
