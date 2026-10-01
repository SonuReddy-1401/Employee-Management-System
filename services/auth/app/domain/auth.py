from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import bcrypt
import jwt
from services.auth.app.config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_jwt_token(user_id: str, role: str, expiry_minutes: int | None = None) -> str:
    minutes = expiry_minutes if expiry_minutes is not None else settings.JWT_EXPIRY_MINUTES
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
