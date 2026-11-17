from collections.abc import AsyncIterator

from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.audios.provider import AudiosProvider
from app.auth.provider import AuthProvider
from app.auth.service.auth import AuthService
from app.config import Settings, settings
from app.core.context import Context
from app.core.engines.database import Transaction
from app.files.provider import FilesProvider
from app.folders.provider import FoldersProvider
from app.folders.repository.folders import FoldersRepository
from app.news.provider import NewsProvider
from app.users.repository.users import UsersRepository
from app.users.service.users import UsersService
from app.videos.provider import VideosProvider


class AppProvider(Provider):
    scope = Scope.APP

    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return settings

    @provide(scope=Scope.APP)
    async def get_engine(self) -> AsyncIterator[AsyncEngine]:
        engine = Transaction().engine
        try:
            yield engine
        finally:
            await engine.dispose()


class RequestProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_transaction(self, engine: AsyncEngine) -> Transaction:
        # Пул соединений общий, состояние транзакции принадлежит одному HTTP-запросу.
        return Transaction(engine=engine)

    @provide
    def get_context(self, request: Request) -> Context:
        return Context(request=request)

    @provide
    def get_users_repository(self, transaction: Transaction, context: Context) -> UsersRepository:
        return UsersRepository(transaction=transaction, context=context)

    @provide
    def get_users_service(self, users_repository: UsersRepository) -> UsersService:
        return UsersService(users_repository=users_repository)

    @provide
    def get_auth_service(
        self,
        users_service: UsersService,
        folders_repository: FoldersRepository,
        config: Settings,
    ) -> AuthService:
        # репозиторий папок нужен регистрации: она создаёт корневую папку
        return AuthService(
            users_service=users_service,
            folders_repository=folders_repository,
            config=config,
        )


def build_dishka_container():
    return make_async_container(
        AppProvider(),
        RequestProvider(),
        AuthProvider(),
        AudiosProvider(),
        FilesProvider(),
        FoldersProvider(),
        NewsProvider(),
        VideosProvider(),
        FastapiProvider(),
    )
