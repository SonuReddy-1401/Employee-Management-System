from typing import Any, Callable, Dict
import jwt
from fastapi import Depends, Request
from ems_common.config import settings
from ems_common.errors import EMSError


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise EMSError(code="TOKEN_EXPIRED", message="Token has expired", status_code=401)
    except jwt.InvalidTokenError:
        raise EMSError(code="INVALID_TOKEN", message="Invalid token", status_code=401)


async def get_current_user(request: Request) -> Dict[str, Any]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise EMSError(code="UNAUTHORIZED", message="Missing or invalid authorization header", status_code=401)

    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)

    if "sub" not in payload or "role" not in payload:
        raise EMSError(code="INVALID_TOKEN", message="Token payload missing required claims", status_code=401)

    return {"user_id": payload["sub"], "role": payload["role"], "claims": payload}


def require_roles(*allowed_roles: str) -> Callable:
    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise EMSError(
                code="FORBIDDEN",
                message=f"Role '{user_role}' is not authorized to access this resource",
                status_code=403,
            )
        return current_user

    return role_checker
