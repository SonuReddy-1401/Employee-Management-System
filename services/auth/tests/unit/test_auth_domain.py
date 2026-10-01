from datetime import datetime, timezone
from uuid import uuid4
import jwt
import pytest
from pydantic import ValidationError
from services.auth.app.config import settings
from services.auth.app.domain.auth import create_jwt_token, hash_password, verify_password
from services.auth.app.schemas.user import UserCreateRequest, UserRole


def test_password_hash_and_verify():
    plain = "SecretPassword123!"
    h1 = hash_password(plain)
    h2 = hash_password(plain)

    assert h1 != plain
    assert h1 != h2  # Different salts per call
    assert verify_password(plain, h1) is True
    assert verify_password(plain, h2) is True
    assert verify_password("WrongPassword!", h1) is False


def test_create_jwt_token_claims_and_expiry():
    user_id = str(uuid4())
    role = "ADMIN"
    token = create_jwt_token(user_id=user_id, role=role, expiry_minutes=15)

    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert decoded["sub"] == user_id
    assert decoded["role"] == role
    assert "exp" in decoded
    assert decoded["exp"] > datetime.now(timezone.utc).timestamp()


def test_user_create_request_role_validation():
    user_id = uuid4()

    # Valid roles
    for role in [UserRole.ADMIN, UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE]:
        req = UserCreateRequest(
            id=user_id, email="test@example.com", password="password123", role=role
        )
        assert req.role == role

    # Invalid password (too short)
    with pytest.raises(ValidationError):
        UserCreateRequest(id=user_id, email="test@example.com", password="short", role=UserRole.EMPLOYEE)

    # Invalid role
    with pytest.raises(ValidationError):
        UserCreateRequest(
            id=user_id, email="test@example.com", password="password123", role="SUPERADMIN"  # type: ignore
        )
