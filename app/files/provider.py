from dishka import Provider, Scope, provide

from app.config import Settings
from app.core.context import Context
from app.core.engines.database import Transaction
from app.files.repository.files import FilesRepository
from app.files.service.files import FilesService
from app.files.storage import FileStorage


class FilesProvider(Provider):
    """Файловое S3-хранилище и файловый сервис."""

    @provide(scope=Scope.APP)
    def get_file_storage(self, config: Settings) -> FileStorage:
        return FileStorage(config=config)

    @provide(scope=Scope.REQUEST)
    def get_files_repository(self, transaction: Transaction, context: Context) -> FilesRepository:
        return FilesRepository(transaction=transaction, context=context)

    @provide(scope=Scope.REQUEST)
    def get_files_service(
        self,
        files_repository: FilesRepository,
        file_storage: FileStorage,
        config: Settings,
    ) -> FilesService:
        return FilesService(
            files_repository=files_repository, file_storage=file_storage, config=config
        )
