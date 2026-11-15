from pathlib import Path
from uuid import UUID, uuid4

from app.config import Settings
from app.core.dependencies import Paginator
from app.core.enums import EFileType, EUserRole
from app.core.exceptions import ForbiddenException, ValidationException
from app.core.schemes import PaginatedSchema
from app.files.constants import (
    FILE_TYPES_HINT,
    IMAGE_TYPES_HINT,
    content_type_for,
    file_type_by_extension,
    is_image_type,
)
from app.files.repository.files import FilesRepository
from app.files.schema.files import (
    FileCreateSchema,
    FileFilterSchema,
    FileResponseSchema,
    FileTypeSchema,
    FileUpdateSchema,
)
from app.files.storage import FileStorage
from app.users.schema.users import UserResponseSchema


class FilesService:
    """Загрузка, выдача, переименование и удаление файлов в S3-хранилище."""

    def __init__(
        self,
        *,
        files_repository: FilesRepository,
        file_storage: FileStorage,
        config: Settings,
    ):
        self._files_repository = files_repository
        self._file_storage = file_storage
        self._max_size = config.FILE_MAX_SIZE_MB * 1024 * 1024

    async def upload(self, *, name: str, filename: str | None, data: bytes) -> FileResponseSchema:
        """Кладёт файл в хранилище и сохраняет запись о нём."""
        file_type = self._resolve_file_type(filename)
        self._validate_content(data=data)

        object_key = f'{uuid4().hex}.{file_type.value}'
        await self._file_storage.upload(
            object_id=object_key, data=data, content_type=content_type_for(file_type)
        )
        return await self._files_repository.create_one(
            data=FileCreateSchema(
                name=name, object_key=object_key, type=file_type, size=len(data)
            )
        )

    async def get_list(
        self, *, filters: FileFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[FileResponseSchema]:
        return await self._files_repository.get_list(filters=filters, paginator=paginator)

    def get_types(self) -> list[FileTypeSchema]:
        """Справочник разрешённых типов файлов.

        Фронтенд строит по нему фильтр списка (`?type=`), атрибут `accept` формы
        загрузки и понимает, какие файлы можно показывать в `<img>`.
        """
        return [
            FileTypeSchema(
                value=file_type,
                content_type=content_type_for(file_type),
                is_image=is_image_type(file_type),
            )
            for file_type in EFileType
        ]

    async def get_many(self, *, pks: list[UUID]) -> list[FileResponseSchema]:
        """Возвращает существующие файлы по списку id (для связей и проверок)."""
        return await self._files_repository.get_many(pks=pks)

    async def download(self, *, pk: UUID) -> tuple[FileResponseSchema, bytes]:
        """Возвращает запись о файле и его содержимое."""
        file = await self._files_repository.get_one(pk=pk)
        data = await self._file_storage.download(object_id=file.object_key)
        return file, data

    async def get_image(self, *, pk: UUID) -> tuple[FileResponseSchema, bytes]:
        """Возвращает изображение и его содержимое для показа в браузере.

        Отдавать инлайном можно только картинки: документы, которые браузер не
        отрисует, получают отказ — для них есть ``download``.
        """
        file, data = await self.download(pk=pk)
        if not is_image_type(file.type):
            raise ValidationException(
                detail=f'Файл не является изображением. Разрешены: {IMAGE_TYPES_HINT}.'
            )
        return file, data

    async def update(
        self, *, pk: UUID, data: FileUpdateSchema, user: UserResponseSchema
    ) -> FileResponseSchema:
        """Переименовывает файл: админ — любой, пользователь — только свой."""
        await self._ensure_can_modify(
            pk=pk, user=user, detail='Можно переименовывать только свои файлы.'
        )
        return await self._files_repository.update_one(pk=pk, data=data)

    async def delete(self, *, pk: UUID, user: UserResponseSchema) -> None:
        """Удаляет файл: админ — любой, пользователь — только свой.

        Чужой файл даёт `403`: файлы и так доступны по id, скрывать факт
        их существования смысла нет.
        """
        await self._ensure_can_modify(
            pk=pk, user=user, detail='Можно удалять только свои файлы.'
        )
        await self.delete_many(pks=[pk])

    async def delete_many(self, *, pks: list[UUID]) -> None:
        """Удаляет файлы из хранилища и помечает их записи удалёнными.

        Нужно при каскадном удалении папки: там сразу уходят все файлы ветки,
        и объекты из S3 убираются теми же правилами, что у `DELETE /api/files`.
        """
        if not pks:
            return

        files = await self._files_repository.delete_many(pks=pks)
        for file in files:
            await self._file_storage.remove(object_id=file.object_key)

    async def _ensure_can_modify(
        self, *, pk: UUID, user: UserResponseSchema, detail: str
    ) -> None:
        """Проверяет право менять файл: админ — любой, остальные — только свой.

        Чужой файл даёт `403` (а не `404`), потому что файлы и так доступны по id.
        Несуществующий файл даёт `404` из репозитория — до проверки прав.
        """
        creator_id = await self._files_repository.get_creator_id(pk=pk)
        if user.role is not EUserRole.ADMIN and creator_id != user.id:
            raise ForbiddenException(detail=detail)

    @staticmethod
    def _resolve_file_type(filename: str | None) -> EFileType:
        file_type = file_type_by_extension(Path(filename or '').suffix)
        if file_type is None:
            raise ValidationException(
                detail=f'Недопустимый тип файла. Разрешены: {FILE_TYPES_HINT}.'
            )
        return file_type

    def _validate_content(self, *, data: bytes) -> None:
        if not data:
            raise ValidationException(detail='Файл пустой.')
        if len(data) > self._max_size:
            raise ValidationException(
                detail=f'Размер файла превышает {self._max_size // (1024 * 1024)} МБ.'
            )
