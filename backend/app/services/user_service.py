from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityAlreadyExistsException, UnauthorizedException
from app.core.security import verify_password
from app.models.user import User
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate, UserLogin


class UserService:
    @staticmethod
    async def register(db: AsyncSession, user_in: UserCreate) -> User:
        existing = await user_repository.get_by_email(db, email=user_in.email)
        if existing:
            raise EntityAlreadyExistsException("User", "email", user_in.email)
        return await user_repository.create_user(db, obj_in=user_in)

    @staticmethod
    async def authenticate(db: AsyncSession, login_data: UserLogin) -> User:
        user = await user_repository.get_by_email(db, email=login_data.email)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise UnauthorizedException("Incorrect email or password")
        if not user.is_active:
            raise UnauthorizedException("Inactive user account")
        return user


user_service = UserService()
