"""
Auth API endpoints: login, get current user, update profile.
Also provides shared auth dependencies used across the app.
"""

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (create_access_token, decode_access_token,
                               get_password_hash, verify_password)
from app.db.database import get_db
from app.models import Runner
from app.models.user import User, UserRole
from app.schemas.auth import (LoginRequest, TokenResponse, UserResponse,
                              UserUpdate)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_active_entity(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Union[User, Runner]:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    entity_type = payload.get("type", "user")

    if sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if entity_type == "runner":
        result = await db.execute(select(Runner).where(Runner.account == sub))
        entity = result.scalar_one_or_none()
    else:
        try:
            entity_id = int(sub)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")
        result = await db.execute(select(User).where(User.id == entity_id))
        entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entity not found")

    # Both models have is_active
    if not entity.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return entity


async def get_current_user(
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
) -> User:
    if not isinstance(current_entity, User):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User privileges required.",
        )
    return current_entity


def require_role(*roles: UserRole):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return current_user

    return role_checker


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated"
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.email is not None:
        existing = await db.execute(
            select(User).where(User.email == data.email, User.id != current_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = data.email

    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
