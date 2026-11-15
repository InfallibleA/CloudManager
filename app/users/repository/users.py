from uuid import UUID

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.users.model.user import User
from app.users.schema.users import (
    UserCreateInternalSchema,
    UserCredentialsSchema,
    UserFilterSchema,
    UserResponseSchema,
)


class UsersRepository(SoftBaseRepository):
    def __init__(self, transaction: Transaction, context: Context):
        super().__init__(model_class=User, transaction=transaction, context=context)

    async def create_one(
        self, *, data: UserCreateInternalSchema, creator_id: UUID | None = None
    ) -> UserResponseSchema:
        """Создаёт пользователя; создатель — явный creator_id или текущий пользователь."""
        return await self._create_one(data, UserResponseSchema, creator_id=creator_id)

    async def get_one(self, *, pk: UUID) -> UserResponseSchema:
        return await self._get_one(pk, UserResponseSchema, scalars=True)

    async def set_blocked(self, *, pk: UUID, blocked: bool) -> UserResponseSchema:
        """Меняет статус блокировки; неизвестный пользователь даёт 404."""
        await self.has_one(pk, raise_error=True)
        return await self._update_one(pk, {'is_blocked': blocked}, UserResponseSchema)

    async def get_list(
        self, *, filters: UserFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[UserResponseSchema]:
        """Постраничный список неудалённых пользователей в порядке логина."""
        db_model = self._model_class
        conditions = []
        if filters.login:
            conditions.append(db_model.login.ilike(f'%{filters.login}%'))
        if filters.role is not None:
            conditions.append(db_model.role == filters.role)

        return await self._get_list(
            *conditions,
            schema=UserResponseSchema,
            scalars=True,
            paginator=paginator,
            transform_query=lambda query: query.order_by(db_model.login),
        )

    async def get_by_login(self, *, login: str) -> UserCredentialsSchema | None:
        users = await self._get_list(
            self._model_class.login == login, schema=UserCredentialsSchema, scalars=True
        )
        return users[0] if users else None

    async def has_login(self, *, login: str) -> bool:
        return await self._exists(self._model_class.login == login)
