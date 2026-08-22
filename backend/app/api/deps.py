from typing import AsyncGenerator, Optional
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User, UserRole
from app.repositories.user_repository import user_repository
from app.schemas.user import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Dependency that decodes JWT token and returns the current authenticated User."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise UnauthorizedException("Could not validate credentials")

    if token_data.sub is None:
        raise UnauthorizedException("Token payload missing subject")

    user = await user_repository.get_by_email(db, email=token_data.sub)
    if not user:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("Inactive user")
    return user


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional),
) -> User:
    """Dependency that returns authenticated user or creates a default demo user for playground access."""
    if token:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
            if token_data.sub:
                user = await user_repository.get_by_email(db, email=token_data.sub)
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # Ensure a default demo user exists for interactive demo screening
    demo_email = "recruiter@resumescreener.ai"
    demo_user = await user_repository.get_by_email(db, email=demo_email)
    if not demo_user:
        from app.schemas.user import UserCreate

        demo_user = await user_repository.create_user(
            db,
            obj_in=UserCreate(
                email=demo_email,
                full_name="Demo AI Recruiter",
                password="demo-password-12345",
                company_name="Smart Talent Corp",
                role=UserRole.RECRUITER,
            ),
        )
    return demo_user


def require_role(*allowed_roles: UserRole):
    """Dependency factory that restricts endpoint access to specified user roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"User role '{current_user.role.value}' does not have required permissions"
            )
        return current_user

    return role_checker
