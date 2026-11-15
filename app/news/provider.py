from dishka import Provider, Scope, provide

from app.core.context import Context
from app.core.engines.database import Transaction
from app.files.service.files import FilesService
from app.news.repository.news import NewsRepository
from app.news.service.news import NewsService


class NewsProvider(Provider):
    """Новости: репозиторий и сервис (файлы берутся из FilesProvider)."""

    @provide(scope=Scope.REQUEST)
    def get_news_repository(self, transaction: Transaction, context: Context) -> NewsRepository:
        return NewsRepository(transaction=transaction, context=context)

    @provide(scope=Scope.REQUEST)
    def get_news_service(
        self, news_repository: NewsRepository, files_service: FilesService
    ) -> NewsService:
        return NewsService(news_repository=news_repository, files_service=files_service)
