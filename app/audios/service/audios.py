import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.audios.constants import AUDIO_TYPES_HINT, audio_type_by_extension, content_type_for
from app.audios.repository.audios import AudiosRepository
from app.audios.schema.audios import (
    AudioCreateSchema,
    AudioFilterSchema,
    AudioPlaybackSchema,
    AudioResponseSchema,
    AudioTypeSchema,
    AudioUpdateSchema,
)
from app.config import Settings
from app.core.dependencies import Paginator
from app.core.enums import EAudioType, EUserRole
from app.core.exceptions import ForbiddenException, UniqueConstraintException, ValidationException
from app.core.schemes import PaginatedSchema
from app.files.storage import FileStorage
from app.folders.repository.folders import FoldersRepository
from app.users.schema.users import UserResponseSchema

# Имя аудио уникально среди активных записей: при дубле отвечаем 409
NAME_CONFLICT_CODE = 409


class AudiosService:
    """Загрузка, выдача, переименование и удаление аудио в S3-хранилище."""

    def __init__(
        self,
        *,
        audios_repository: AudiosRepository,
        folders_repository: FoldersRepository,
        file_storage: FileStorage,
        config: Settings,
    ):
        self._audios_repository = audios_repository
        self._folders_repository = folders_repository
        self._file_storage = file_storage
        self._max_size = config.AUDIO_MAX_SIZE_MB * 1024 * 1024
        self._presign_ttl = config.AUDIO_PRESIGN_TTL_SECONDS

    async def upload(
        self,
        *,
        name: str,
        filename: str | None,
        stream: BinaryIO,
        size: int | None,
        folder_id: UUID | None = None,
    ) -> AudioResponseSchema:
        """Кладёт аудио в хранилище и сохраняет запись о нём.

        Имя уникально: дубль отсекаем до загрузки объекта, чтобы не оставлять
        «сироту» в S3-хранилище. `folder_id` сразу кладёт аудио в папку пользователя.
        """
        audio_type = self._resolve_audio_type(filename)
        if await self._audios_repository.exists_by_name(name=name):
            raise self._name_conflict(name=name)
        if folder_id is not None:
            await self._ensure_folder(folder_id=folder_id)

        length = self._resolve_size(stream=stream, size=size)
        self._validate_size(length=length)

        object_key = f'audios/{uuid4().hex}.{audio_type.value}'
        stream.seek(0)
        audio: AudioResponseSchema | None = None
        try:
            await self._file_storage.upload_stream(
                object_id=object_key,
                stream=stream,
                length=length,
                content_type=content_type_for(audio_type),
            )
            audio = await self._audios_repository.create_one(
                data=AudioCreateSchema(
                    name=name, object_key=object_key, type=audio_type, size=length
                )
            )
            if folder_id is not None:
                await self._folders_repository.attach_audio(folder_id=folder_id, audio_id=audio.id)
        except UniqueConstraintException, IntegrityError:
            # Гонка: имя заняли между проверкой и вставкой — объект не оставляем
            await self._file_storage.remove(object_id=object_key)
            raise self._name_conflict(name=name) from None
        except Exception:
            # Сбой после загрузки объекта: не оставляем ни «сироту» в S3, ни запись без файла
            await self._file_storage.remove(object_id=object_key)
            if audio is not None:
                await self._audios_repository.delete_one(pk=audio.id)
            raise
        return audio

    async def get_list(
        self, *, filters: AudioFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[AudioResponseSchema]:
        return await self._audios_repository.get_list(filters=filters, paginator=paginator)

    async def get_one(self, *, pk: UUID) -> AudioResponseSchema:
        return await self._audios_repository.get_one(pk=pk)

    async def get_many(self, *, pks: list[UUID]) -> list[AudioResponseSchema]:
        """Возвращает существующие аудио по списку id (для связей и проверок)."""
        return await self._audios_repository.get_many(pks=pks)

    async def get_one_by_name(self, *, name: str) -> AudioResponseSchema:
        return await self._audios_repository.get_one_by_name(name=name)

    def get_types(self) -> list[AudioTypeSchema]:
        """Справочник разрешённых типов аудио для фильтра и атрибута `accept`."""
        return [
            AudioTypeSchema(value=audio_type, content_type=content_type_for(audio_type))
            for audio_type in EAudioType
        ]

    async def get_playback(self, *, pk: UUID) -> AudioPlaybackSchema:
        """Возвращает presigned-ссылку: клиент воспроизводит аудио напрямую из S3."""
        audio = await self._audios_repository.get_one(pk=pk)
        return AudioPlaybackSchema(
            url=self._file_storage.presign_get(
                object_id=audio.object_key, expires_seconds=self._presign_ttl
            ),
            content_type=content_type_for(audio.type),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._presign_ttl),
            expires_in=self._presign_ttl,
        )

    async def update(
        self, *, pk: UUID, data: AudioUpdateSchema, user: UserResponseSchema
    ) -> AudioResponseSchema:
        """Переименовывает аудио: админ — любое, пользователь — только своё."""
        await self._ensure_can_modify(
            pk=pk, user=user, detail='Можно переименовывать только свои аудио.'
        )
        if data.name is not None and await self._audios_repository.exists_by_name(
            name=data.name, exclude_id=pk
        ):
            raise self._name_conflict(name=data.name)
        try:
            return await self._audios_repository.update_one(pk=pk, data=data)
        except UniqueConstraintException, IntegrityError:
            assert data.name is not None
            raise self._name_conflict(name=data.name) from None

    async def delete(self, *, pk: UUID, user: UserResponseSchema) -> None:
        """Удаляет запись и объект из хранилища: админ — любое, пользователь — только своё."""
        await self._ensure_can_modify(pk=pk, user=user, detail='Можно удалять только свои аудио.')
        audio = await self._audios_repository.delete_one(pk=pk)
        await self._file_storage.remove(object_id=audio.object_key)

    async def delete_many(self, *, pks: list[UUID]) -> None:
        """Удаляет аудио из хранилища и помечает их записи удалёнными (при удалении папки)."""
        if not pks:
            return

        audios = await self._audios_repository.delete_many(pks=pks)
        for audio in audios:
            await self._file_storage.remove(object_id=audio.object_key)

    async def _ensure_can_modify(self, *, pk: UUID, user: UserResponseSchema, detail: str) -> None:
        """Проверяет право менять или удалять аудио: админ — любое, остальные — только своё."""
        creator_id = await self._audios_repository.get_creator_id(pk=pk)
        if user.role is not EUserRole.ADMIN and creator_id != user.id:
            raise ForbiddenException(detail=detail)

    async def _ensure_folder(self, *, folder_id: UUID) -> None:
        """Проверяет, что папка существует и принадлежит текущему пользователю."""
        if not await self._folders_repository.has_one(folder_id):
            raise ValidationException(detail=f'Папка не найдена: {folder_id}.')

    @staticmethod
    def _resolve_audio_type(filename: str | None) -> EAudioType:
        audio_type = audio_type_by_extension(Path(filename or '').suffix)
        if audio_type is None:
            raise ValidationException(
                detail=f'Недопустимый тип аудио. Разрешены: {AUDIO_TYPES_HINT}.'
            )
        return audio_type

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
            detail=f'Аудио с именем «{name}» уже существует.', code=NAME_CONFLICT_CODE
        )
