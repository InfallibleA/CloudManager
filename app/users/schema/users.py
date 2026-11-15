from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.enums import EUserRole
from app.core.exceptions import ForbiddenException
from app.core.schemes.base import CloudManagerBaseModel


class UserCreateSchema(CloudManagerBaseModel):
    """Данные для создания пользователя (CLI и саморегистрация)."""

    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserCreateInternalSchema(CloudManagerBaseModel):
    """Данные для создания пользователя внутри приложения (пароль уже захеширован)."""

    login: str
    password_hash: str
    role: EUserRole = EUserRole.CLIENT


class UserCredentialsSchema(CloudManagerBaseModel):
    """Учётные данные пользователя. Наружу не отдаётся."""

    id: UUID
    login: str
    password_hash: str
    is_blocked: bool = False


class UserFilterSchema(CloudManagerBaseModel):
    """Фильтры списка пользователей."""

    login: str | None = Field(default=None, max_length=255)
    """Поиск по логину: вхождение подстроки без учёта регистра."""

    role: EUserRole | None = None


class UserResponseSchema(CloudManagerBaseModel):
    """Публичное представление пользователя."""

    id: UUID
    login: str
    role: EUserRole
    is_blocked: bool = False
    """Заблокированный пользователь не может войти и пользоваться API."""
    created_at: datetime


class AdminUserSchema(UserResponseSchema):
    """Текущий пользователь, проверенный на роль администратора."""

    @classmethod
    def from_user(cls, user: UserResponseSchema) -> 'AdminUserSchema':
        """Возвращает пользователя как администратора или бросает ForbiddenException."""
        if user.role is not EUserRole.ADMIN:
            raise ForbiddenException(detail='Действие доступно только администратору.')
        return cls.model_validate(user, from_attributes=True)
