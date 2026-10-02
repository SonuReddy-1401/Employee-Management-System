import uuid
import httpx
import pytest
from tests.contract.conftest import AUTH_URL, ADMIN_EMAIL, ADMIN_PASSWORD
from tests.contract.schema_helper import validate_schema


def test_auth_login_success():
    with httpx.Client() as client:
        resp = client.post(f"{AUTH_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        validate_schema(data, "login-response.json")


def test_auth_login_invalid_credentials():
    with httpx.Client() as client:
        resp = client.post(f"{AUTH_URL}/auth/login", json={"email": "wrong@ems.com", "password": "WrongPassword123!"})
        assert resp.status_code == 401
        data = resp.json()
        validate_schema(data, "error-response.json")


def test_auth_internal_users_lifecycle():
    user_id = str(uuid.uuid4())
    email = f"authuser.{uuid.uuid4().hex[:6]}@auth.test.com"
    payload = {
        "id": user_id,
        "email": email,
        "password": "Password123!",
        "role": "EMPLOYEE"
    }

    with httpx.Client() as client:
        # Create user -> 201
        resp = client.post(f"{AUTH_URL}/internal/users", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        validate_schema(data, "created-user.json")

        # Duplicate user -> 409
        resp_dup = client.post(f"{AUTH_URL}/internal/users", json=payload)
        assert resp_dup.status_code == 409
        validate_schema(resp_dup.json(), "error-response.json")


def test_auth_internal_users_repeated_delete():
    user_id = str(uuid.uuid4())
    with httpx.Client() as client:
        resp1 = client.delete(f"{AUTH_URL}/internal/users/{user_id}")
        assert resp1.status_code == 204
        assert resp1.text == ""

        resp2 = client.delete(f"{AUTH_URL}/internal/users/{user_id}")
        assert resp2.status_code == 204
        assert resp2.text == ""
