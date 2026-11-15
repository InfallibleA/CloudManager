from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.service.auth import AuthService
from app.config import Settings
from app.core.enums import EUserRole
from app.core.exceptions import BaseOrderException, UnauthorizedException
from app.core.exceptions_handlers import order_exception_handler
from app.files.repository.files import FilesRepository
from app.files.service.files import FilesService
from app.files.storage import FileStorage
from app.folders.repository.folders import FoldersRepository
from app.folders.service.folders import FoldersService
from app.news.repository.news import NewsRepository
from app.news.service.news import NewsService
from app.routers import router
from app.users.repository.users import UsersRepository
from app.users.schema.users import AdminUserSchema, UserResponseSchema
from app.users.service.users import UsersService
from app.videos.repository.videos import VideosRepository
from app.videos.service.videos import VideosService
from tests.fakes import (
    FakeFilesRepository,
    FakeFileStorage,
    FakeFoldersRepository,
    FakeNewsRepository,
    FakeUsersRepository,
    FakeVideosRepository,
)

ADMIN_USER_ID = UUID('00000000-0000-0000-0000-000000000001')
CLIENT_USER_ID = UUID('00000000-0000-0000-0000-000000000002')


def build_test_settings(**overrides: Any) -> Settings:
    """Настройки для тестов: не зависят от локального .env.

    Переданные именованные аргументы перекрывают значения по умолчанию.
    """
    return Settings(
        DB_SCHEME='postgresql+asyncpg',
        POSTGRES_HOST='localhost',
        POSTGRES_PORT=5432,
        POSTGRES_DB='cloud_manager',
        POSTGRES_USER='cloud_manager',
        POSTGRES_PASSWORD='cloud_manager',
        DB_POOL_SIZE=1,
        DB_MAX_OVERFLOW=0,
        APP_HOST='127.0.0.1',
        APP_PORT=8000,
        APP_NAME='cloud_manager',
        APP_VERSION='test',
        JWT_SECRET_KEY='test-secret-key',
        S3_ACCESS_KEY='test-access-key',
        S3_SECRET_KEY='test-secret-key',
        S3_PUBLIC_ENDPOINT='http://test',
        FILE_MAX_SIZE_MB=1,
        VIDEO_MAX_SIZE_MB=1,
        VIDEO_PRESIGN_TTL_SECONDS=3600,
        **overrides,
    )


class TestProvider(Provider):
    """Подменяет хранилище и БД, а текущим пользователем отдаёт фикстуру.

    `user=None` имитирует запрос без токена: зависимость пользователя отвечает 401,
    как это делает `AuthProvider.get_current_user` при отсутствии заголовка.
    """

    def __init__(
        self,
        *,
        storage: FileStorage,
        repository: FilesRepository,
        folders_repository: FakeFoldersRepository,
        news_repository: NewsRepository,
        videos_repository: VideosRepository,
        users_repository: UsersRepository,
        user: UserResponseSchema | None,
    ):
        super().__init__()
        self._storage = storage
        self._repository = repository
        self._folders_repository = folders_repository
        self._news_repository = news_repository
        self._videos_repository = videos_repository
        self._users_repository = users_repository
        self._user = user

    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return build_test_settings()

    @provide(scope=Scope.APP)
    def get_file_storage(self) -> FileStorage:
        return self._storage

    @provide(scope=Scope.REQUEST)
    def get_files_repository(self) -> FilesRepository:
        return self._repository

    @provide(scope=Scope.REQUEST)
    def get_files_service(
        self, files_repository: FilesRepository, file_storage: FileStorage, config: Settings
    ) -> FilesService:
        return FilesService(
            files_repository=files_repository, file_storage=file_storage, config=config
        )

    @provide(scope=Scope.REQUEST)
    def get_folders_repository(self) -> FoldersRepository:
        # владельца и роль фейку выставляет get_current_user (как Context в реальном коде):
        # регистрация идёт без пользователя, поэтому зависимость от него здесь недопустима
        return self._folders_repository

    @provide(scope=Scope.REQUEST)
    def get_folders_service(
        self, folders_repository: FoldersRepository, files_service: FilesService
    ) -> FoldersService:
        return FoldersService(
            folders_repository=folders_repository, files_service=files_service
        )

    @provide(scope=Scope.REQUEST)
    def get_news_repository(self) -> NewsRepository:
        return self._news_repository

    @provide(scope=Scope.REQUEST)
    def get_news_service(
        self, news_repository: NewsRepository, files_service: FilesService
    ) -> NewsService:
        return NewsService(news_repository=news_repository, files_service=files_service)

    @provide(scope=Scope.REQUEST)
    def get_users_repository(self) -> UsersRepository:
        return self._users_repository

    @provide(scope=Scope.REQUEST)
    def get_users_service(self, users_repository: UsersRepository) -> UsersService:
        return UsersService(users_repository=users_repository)

    @provide(scope=Scope.REQUEST)
    def get_auth_service(
        self,
        users_service: UsersService,
        folders_repository: FoldersRepository,
        config: Settings,
    ) -> AuthService:
        return AuthService(
            users_service=users_service,
            folders_repository=folders_repository,
            config=config,
        )

    @provide(scope=Scope.REQUEST)
    def get_current_user(self) -> UserResponseSchema:
        if self._user is None:
            raise UnauthorizedException()
        # фейк файлов: создателем новых файлов становится текущий пользователь
        self._repository.use_owner(owner_id=self._user.id, login=self._user.login)
        # фейк папок: владельцем папок тоже становится пользователь запроса
        self._folders_repository.use_owner(owner_id=self._user.id)
        self._folders_repository.use_admin(is_admin=self._user.role is EUserRole.ADMIN)
        return self._user

    @provide(scope=Scope.REQUEST)
    def get_videos_repository(self) -> VideosRepository:
        return self._videos_repository

    @provide(scope=Scope.REQUEST)
    def get_videos_service(
        self, videos_repository: VideosRepository, file_storage: FileStorage, config: Settings
    ) -> VideosService:
        return VideosService(
            videos_repository=videos_repository, file_storage=file_storage, config=config
        )

    @provide(scope=Scope.REQUEST)
    def get_admin_user(self, user: UserResponseSchema) -> AdminUserSchema:
        return AdminUserSchema.from_user(user)


@pytest.fixture
def fake_storage() -> FakeFileStorage:
    return FakeFileStorage()


@pytest.fixture
def fake_repository() -> FakeFilesRepository:
    return FakeFilesRepository()


@pytest.fixture
def fake_folders_repository(fake_repository: FakeFilesRepository) -> FakeFoldersRepository:
    return FakeFoldersRepository(files_repository=fake_repository)


@pytest.fixture
def fake_news_repository(fake_repository: FakeFilesRepository) -> FakeNewsRepository:
    return FakeNewsRepository(files_repository=fake_repository)


@pytest.fixture
def fake_videos_repository() -> FakeVideosRepository:
    return FakeVideosRepository()


@pytest.fixture
def fake_users_repository() -> FakeUsersRepository:
    return FakeUsersRepository()


@pytest.fixture
def admin_user() -> UserResponseSchema:
    return UserResponseSchema(
        id=ADMIN_USER_ID,
        login='admin',
        role=EUserRole.ADMIN,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def client_user() -> UserResponseSchema:
    return UserResponseSchema(
        id=CLIENT_USER_ID,
        login='client',
        role=EUserRole.CLIENT,
        created_at=datetime.now(timezone.utc),
    )


@asynccontextmanager
async def build_client(
    *,
    user: UserResponseSchema | None,
    storage: FileStorage,
    repository: FilesRepository,
    folders_repository: FakeFoldersRepository,
    news_repository: NewsRepository,
    videos_repository: VideosRepository,
    users_repository: UsersRepository,
) -> AsyncIterator[AsyncClient]:
    """Поднимает приложение с подменёнными зависимостями и текущим пользователем."""
    container = make_async_container(
        TestProvider(
            storage=storage,
            repository=repository,
            folders_repository=folders_repository,
            news_repository=news_repository,
            videos_repository=videos_repository,
            users_repository=users_repository,
            user=user,
        )
    )
    app = FastAPI()
    app.add_exception_handler(BaseOrderException, order_exception_handler)
    setup_dishka(container=container, app=app)
    app.include_router(router)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as http_client:
            yield http_client
    finally:
        await container.close()


@pytest.fixture
async def client(
    fake_storage: FakeFileStorage,
    fake_repository: FakeFilesRepository,
    fake_folders_repository: FakeFoldersRepository,
    fake_news_repository: FakeNewsRepository,
    fake_videos_repository: FakeVideosRepository,
    fake_users_repository: FakeUsersRepository,
    admin_user: UserResponseSchema,
) -> AsyncIterator[AsyncClient]:
    """Клиент API от лица администратора."""
    async with build_client(
        user=admin_user,
        storage=fake_storage,
        repository=fake_repository,
        folders_repository=fake_folders_repository,
        news_repository=fake_news_repository,
        videos_repository=fake_videos_repository,
        users_repository=fake_users_repository,
    ) as http_client:
        yield http_client


@pytest.fixture
async def client_as_client(
    fake_storage: FakeFileStorage,
    fake_repository: FakeFilesRepository,
    fake_folders_repository: FakeFoldersRepository,
    fake_news_repository: FakeNewsRepository,
    fake_videos_repository: FakeVideosRepository,
    fake_users_repository: FakeUsersRepository,
    client_user: UserResponseSchema,
) -> AsyncIterator[AsyncClient]:
    """Клиент API от лица пользователя с ролью client."""
    async with build_client(
        user=client_user,
        storage=fake_storage,
        repository=fake_repository,
        folders_repository=fake_folders_repository,
        news_repository=fake_news_repository,
        videos_repository=fake_videos_repository,
        users_repository=fake_users_repository,
    ) as http_client:
        yield http_client


@pytest.fixture
async def client_without_token(
    fake_storage: FakeFileStorage,
    fake_repository: FakeFilesRepository,
    fake_folders_repository: FakeFoldersRepository,
    fake_news_repository: FakeNewsRepository,
    fake_videos_repository: FakeVideosRepository,
    fake_users_repository: FakeUsersRepository,
) -> AsyncIterator[AsyncClient]:
    """Клиент API без токена: запросы к защищённым ручкам получают 401."""
    async with build_client(
        user=None,
        storage=fake_storage,
        repository=fake_repository,
        folders_repository=fake_folders_repository,
        news_repository=fake_news_repository,
        videos_repository=fake_videos_repository,
        users_repository=fake_users_repository,
    ) as http_client:
        yield http_client
