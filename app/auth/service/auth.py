from uuid import UUID

from app.auth.schema.auth import LoginSchema, TokenResponseSchema
from app.auth.security import (
    create_access_token,
    decode_access_token,
    get_dummy_password_hash,
    hash_password,
    verify_password,
)
from app.config import Settings
from app.core.exceptions import (
    ForbiddenException,
    UnauthorizedException,
    UniqueConstraintException,
)
from app.folders.repository.folders import FoldersRepository
from app.users.schema.users import (
    UserCreateSchema,
    UserResponseSchema,
)
from app.users.service.users import UsersService


class AuthService:
    def __init__(
        self,
        *,
        users_service: UsersService,
        folders_repository: FoldersRepository,
        config: Settings,
    ):
        self._users_service = users_service
        self._folders_repository = folders_repository
        self._config = config

    async def create_admin(self, *, data: UserCreateSchema) -> UserResponseSchema:
        """Создаёт администратора от лица ROOT_USER. Саморегистрация недоступна."""
        if await self._users_service.has_login(login=data.login):
            raise UniqueConstraintException(fields=['login'])

        user = await self._users_service.create_admin(
            login=data.login, password_hash=hash_password(data.password)
        )
        await self._create_root_folder(user=user)
        return user

    async def register(self, *, data: UserCreateSchema) -> UserResponseSchema:
        """Открытая саморегистрация: создаёт пользователя с ролью client.

        Вместе с пользователем создаётся его корневая папка — всё дерево папок
        и файлов дальше строится внутри неё.
        """
        if await self._users_service.has_login(login=data.login):
            raise UniqueConstraintException(fields=['login'])

        user = await self._users_service.create_client(
            login=data.login, password_hash=hash_password(data.password)
        )
        await self._create_root_folder(user=user)
        return user

    async def _create_root_folder(self, *, user: UserResponseSchema) -> None:
        """Личная корневая папка пользователя: называется по его логину."""
        await self._folders_repository.create_root(owner_id=user.id, name=user.login)

    async def login(self, *, data: LoginSchema) -> TokenResponseSchema:
        """Проверяет учётные данные и выдаёт JWT."""
        credentials = await self._users_service.get_credentials(login=data.login)
        password_hash = credentials.password_hash if credentials else get_dummy_password_hash()

        if not verify_password(password=data.password, password_hash=password_hash):
            raise UnauthorizedException(detail='Неверный логин или пароль.')
        if credentials.is_blocked:
            raise ForbiddenException(detail='Пользователь заблокирован.')

        return self._issue_token(user_id=credentials.id)

    async def authenticate(self, *, token: str) -> UserResponseSchema:
        """Возвращает пользователя по access-токену."""
        payload = decode_access_token(token=token, config=self._config)
        try:
            user_id = UUID(payload['sub'])
        except (KeyError, TypeError, ValueError) as err:
            raise UnauthorizedException(detail='Некорректный токен.') from err

        user = await self._users_service.get_one(pk=user_id)
        if user.is_blocked:
            raise ForbiddenException(detail='Пользователь заблокирован.')
        return user

    def _issue_token(self, *, user_id: UUID) -> TokenResponseSchema:
        token, expires_in = create_access_token(user_id=user_id, config=self._config)
        return TokenResponseSchema(access_token=token, expires_in=expires_in)
