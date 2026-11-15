from uuid import UUID

from app.core.dependencies import Paginator
from app.core.enums import EUser, EUserRole
from app.core.schemes import PaginatedSchema
from app.users.repository.users import UsersRepository
from app.users.schema.users import (
    UserCreateInternalSchema,
    UserCredentialsSchema,
    UserFilterSchema,
    UserResponseSchema,
)


class UsersService:
    def __init__(self, *, users_repository: UsersRepository):
        self._users_repository = users_repository

    async def create_admin(self, *, login: str, password_hash: str) -> UserResponseSchema:
        """Создаёт администратора от лица ROOT_USER (используется CLI)."""
        return await self._users_repository.create_one(
            data=UserCreateInternalSchema(
                login=login, password_hash=password_hash, role=EUserRole.ADMIN
            ),
            creator_id=EUser.ROOT_USER.value,
        )

    async def create_client(self, *, login: str, password_hash: str) -> UserResponseSchema:
        """Создаёт пользователя-клиента (открытая саморегистрация)."""
        return await self._users_repository.create_one(
            data=UserCreateInternalSchema(
                login=login, password_hash=password_hash, role=EUserRole.CLIENT
            ),
            creator_id=EUser.ROOT_USER.value,
        )

    async def get_one(self, *, pk: UUID) -> UserResponseSchema:
        return await self._users_repository.get_one(pk=pk)

    async def get_list(
        self, *, filters: UserFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[UserResponseSchema]:
        return await self._users_repository.get_list(filters=filters, paginator=paginator)

    async def get_credentials(self, *, login: str) -> UserCredentialsSchema | None:
        return await self._users_repository.get_by_login(login=login)

    async def block(self, *, pk: UUID) -> UserResponseSchema:
        """Блокирует пользователя: вход и все защищённые ручки становятся недоступны."""
        return await self._users_repository.set_blocked(pk=pk, blocked=True)

    async def unblock(self, *, pk: UUID) -> UserResponseSchema:
        """Снимает блокировку."""
        return await self._users_repository.set_blocked(pk=pk, blocked=False)

    async def has_login(self, *, login: str) -> bool:
        return await self._users_repository.has_login(login=login)
