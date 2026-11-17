from dishka import Provider, Scope, provide

from app.audios.repository.audios import AudiosRepository
from app.audios.service.audios import AudiosService
from app.config import Settings
from app.core.context import Context
from app.core.engines.database import Transaction
from app.files.storage import FileStorage
from app.folders.repository.folders import FoldersRepository


class AudiosProvider(Provider):
    """Аудио: репозиторий и сервис поверх общего S3-хранилища."""

    @provide(scope=Scope.REQUEST)
    def get_audios_repository(
        self, transaction: Transaction, context: Context
    ) -> AudiosRepository:
        return AudiosRepository(transaction=transaction, context=context)

    @provide(scope=Scope.REQUEST)
    def get_audios_service(
        self,
        audios_repository: AudiosRepository,
        folders_repository: FoldersRepository,
        file_storage: FileStorage,
        config: Settings,
    ) -> AudiosService:
        return AudiosService(
            audios_repository=audios_repository,
            folders_repository=folders_repository,
            file_storage=file_storage,
            config=config,
        )
