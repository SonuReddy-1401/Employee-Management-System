from uuid import UUID
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.errors import EMSError
from services.auth.app.domain.auth import create_jwt_token, hash_password, verify_password
from services.auth.app.models.user import User
from services.auth.app.repositories.user_repository import UserRepository
from services.auth.app.schemas.user import LoginRequest, TokenResponse, UserCreateRequest, UserResponse

router = APIRouter()


async def get_db():
    raise NotImplementedError("Replaced in main app dependency override")


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_email(payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise EMSError(
            code="UNAUTHORIZED",
            message="Invalid email or password",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = create_jwt_token(user_id=str(user.id), role=user.role)
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/internal/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    existing_email = await repo.get_by_email(payload.email)
    if existing_email:
        raise EMSError(
            code="CONFLICT",
            message="User with this email already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    existing_id = await repo.get_by_id(payload.id)
    if existing_id:
        raise EMSError(
            code="CONFLICT",
            message="User with this id already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    user = User(
        id=payload.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role.value if hasattr(payload.role, "value") else str(payload.role),
    )
    created_user = await repo.create(user)
    return created_user


@router.delete("/internal/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user:
        await repo.delete(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
