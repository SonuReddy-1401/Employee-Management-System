import httpx
import pytest
from tests.contract.conftest import GATEWAY_URL
from tests.contract.schema_helper import validate_schema


def test_gateway_unknown_path_404(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    with httpx.Client() as client:
        resp = client.get(f"{GATEWAY_URL}/nonexistent/path/12345", headers=headers)
        assert resp.status_code == 404
        validate_schema(resp.json(), "error-response.json")



def test_gateway_internal_path_blocked_404():
    with httpx.Client() as client:
        # Try accessing /internal endpoints through the gateway
        resp1 = client.post(f"{GATEWAY_URL}/internal/users", json={})
        assert resp1.status_code == 404
        validate_schema(resp1.json(), "error-response.json")

        resp2 = client.post(f"{GATEWAY_URL}/internal/profiles", json={})
        assert resp2.status_code == 404
        validate_schema(resp2.json(), "error-response.json")


def test_gateway_missing_token_401():
    with httpx.Client() as client:
        resp = client.get(f"{GATEWAY_URL}/employees")
        assert resp.status_code == 401
        validate_schema(resp.json(), "error-response.json")
