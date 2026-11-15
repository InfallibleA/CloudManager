from dishka import Provider, Scope, provide

from app.config import Settings
from app.core.context import Context
from app.core.engines.database import Transaction
from app.files.storage import FileStorage
from app.folders.repository.folders import FoldersRepository
from app.videos.repository.videos import VideosRepository
from app.videos.service.videos import VideosService


class VideosProvider(Provider):
    """Видео: репозиторий и сервис поверх общего S3-хранилища."""

    @provide(scope=Scope.REQUEST)
    def get_videos_repository(
        self, transaction: Transaction, context: Context
    ) -> VideosRepository:
        return VideosRepository(transaction=transaction, context=context)

    @provide(scope=Scope.REQUEST)
    def get_videos_service(
        self,
        videos_repository: VideosRepository,
        folders_repository: FoldersRepository,
        file_storage: FileStorage,
        config: Settings,
    ) -> VideosService:
        return VideosService(
            videos_repository=videos_repository,
            folders_repository=folders_repository,
            file_storage=file_storage,
            config=config,
        )
