import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.core.dependencies import Paginator
from app.core.enums import EUserRole, EVideoType
from app.core.exceptions import ForbiddenException, UniqueConstraintException, ValidationException
from app.core.schemes import PaginatedSchema
from app.files.storage import FileStorage
from app.users.schema.users import UserResponseSchema
from app.videos.constants import VIDEO_TYPES_HINT, content_type_for, video_type_by_extension
from app.videos.repository.videos import VideosRepository
from app.videos.schema.videos import (
    VideoCreateSchema,
    VideoFilterSchema,
    VideoPlaybackSchema,
    VideoResponseSchema,
    VideoTypeSchema,
)

# Имя видео уникально среди активных записей: при дубле отвечаем 409
NAME_CONFLICT_CODE = 409


class VideosService:
    """Загрузка, выдача и удаление видео в S3-хранилище."""

    def __init__(
        self, *, videos_repository: VideosRepository, file_storage: FileStorage, config: Settings
    ):
        self._videos_repository = videos_repository
        self._file_storage = file_storage
        self._max_size = config.VIDEO_MAX_SIZE_MB * 1024 * 1024
        self._presign_ttl = config.VIDEO_PRESIGN_TTL_SECONDS

    async def upload(
        self, *, name: str, filename: str | None, stream: BinaryIO, size: int | None
    ) -> VideoResponseSchema:
        """Кладёт видео в хранилище и сохраняет запись о нём.

        Имя уникально: дубль отсекаем до загрузки объекта, чтобы не оставлять
        «сироту» в S3-хранилище.
        """
        video_type = self._resolve_video_type(filename)
        if await self._videos_repository.exists_by_name(name=name):
            raise self._name_conflict(name=name)

        length = self._resolve_size(stream=stream, size=size)
        self._validate_size(length=length)

        object_key = f'videos/{uuid4().hex}.{video_type.value}'
        stream.seek(0)
        try:
            await self._file_storage.upload_stream(
                object_id=object_key,
                stream=stream,
                length=length,
                content_type=content_type_for(video_type),
            )
            return await self._videos_repository.create_one(
                data=VideoCreateSchema(
                    name=name, object_key=object_key, type=video_type, size=length
                )
            )
        except UniqueConstraintException, IntegrityError:
            # Гонка: имя заняли между проверкой и вставкой — объект не оставляем
            await self._file_storage.remove(object_id=object_key)
            raise self._name_conflict(name=name) from None

    async def get_list(
        self, *, filters: VideoFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[VideoResponseSchema]:
        return await self._videos_repository.get_list(filters=filters, paginator=paginator)

    async def get_one(self, *, pk: UUID) -> VideoResponseSchema:
        return await self._videos_repository.get_one(pk=pk)

    async def get_one_by_name(self, *, name: str) -> VideoResponseSchema:
        return await self._videos_repository.get_one_by_name(name=name)

    async def exists(self, *, pk: UUID) -> bool:
        """Проверяет, что видео существует и не удалено (для ссылок других модулей)."""
        return await self._videos_repository.has_one(pk)

    def get_types(self) -> list[VideoTypeSchema]:
        """Справочник разрешённых типов видео для фильтра и атрибута `accept`."""
        return [
            VideoTypeSchema(value=video_type, content_type=content_type_for(video_type))
            for video_type in EVideoType
        ]

    async def get_playback(self, *, pk: UUID) -> VideoPlaybackSchema:
        """Возвращает presigned-ссылку: браузер играет видео напрямую из S3."""
        video = await self._videos_repository.get_one(pk=pk)
        return VideoPlaybackSchema(
            url=self._file_storage.presign_get(
                object_id=video.object_key, expires_seconds=self._presign_ttl
            ),
            content_type=content_type_for(video.type),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._presign_ttl),
            expires_in=self._presign_ttl,
        )

    async def delete(self, *, pk: UUID, user: UserResponseSchema) -> None:
        """Удаляет запись и объект из хранилища: админ — любое, пользователь — только своё."""
        await self._ensure_can_modify(pk=pk, user=user)
        video = await self._videos_repository.delete_one(pk=pk)
        await self._file_storage.remove(object_id=video.object_key)

    async def _ensure_can_modify(self, *, pk: UUID, user: UserResponseSchema) -> None:
        """Проверяет право удалять видео: админ — любое, остальные — только своё.

        Чужое видео даёт `403` (а не `404`), потому что видео и так доступны по id.
        Несуществующее видео даёт `404` из репозитория — до проверки прав.
        """
        creator_id = await self._videos_repository.get_creator_id(pk=pk)
        if user.role is not EUserRole.ADMIN and creator_id != user.id:
            raise ForbiddenException(detail='Можно удалять только свои видео.')

    @staticmethod
    def _resolve_video_type(filename: str | None) -> EVideoType:
        video_type = video_type_by_extension(Path(filename or '').suffix)
        if video_type is None:
            raise ValidationException(
                detail=f'Недопустимый тип видео. Разрешены: {VIDEO_TYPES_HINT}.'
            )
        return video_type

    @staticmethod
    def _resolve_size(*, stream: BinaryIO, size: int | None) -> int:
        """Размер берём из UploadFile, иначе считаем по потоку без чтения в память."""
        if size is not None:
            return size
        stream.seek(0, os.SEEK_END)
        length = stream.tell()
        stream.seek(0)
        return length

    def _validate_size(self, *, length: int) -> None:
        if length <= 0:
            raise ValidationException(detail='Файл пустой.')
        if length > self._max_size:
            raise ValidationException(
                detail=f'Размер файла превышает {self._max_size // (1024 * 1024)} МБ.'
            )

    @staticmethod
    def _name_conflict(*, name: str) -> UniqueConstraintException:
        return UniqueConstraintException(
            detail=f'Видео с именем «{name}» уже существует.', code=NAME_CONFLICT_CODE
        )
