from dishka import Provider, Scope, provide

from app.audios.service.audios import AudiosService
from app.core.context import Context
from app.core.engines.database import Transaction
from app.files.service.files import FilesService
from app.folders.repository.folders import FoldersRepository
from app.folders.service.folders import FoldersService
from app.videos.service.videos import VideosService


class FoldersProvider(Provider):
    """Папки: репозиторий и сервис (файлы, видео и аудио берутся из своих провайдеров)."""

    @provide(scope=Scope.REQUEST)
    def get_folders_repository(
        self, transaction: Transaction, context: Context
    ) -> FoldersRepository:
        return FoldersRepository(transaction=transaction, context=context)

    @provide(scope=Scope.REQUEST)
    def get_folders_service(
        self,
        folders_repository: FoldersRepository,
        files_service: FilesService,
        videos_service: VideosService,
        audios_service: AudiosService,
    ) -> FoldersService:
        return FoldersService(
            folders_repository=folders_repository,
            files_service=files_service,
            videos_service=videos_service,
            audios_service=audios_service,
        )
