from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.audios.schema.audios import AudioShortSchema
from app.core.schemes.base import CloudManagerBaseModel
from app.files.schema.files import FileShortSchema
from app.videos.schema.videos import VideoShortSchema


class FolderCreateSchema(CloudManagerBaseModel):
    """Данные для создания папки."""

    name: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None
    """Родительская папка: `null` — внутри корневой папки пользователя."""
    file_ids: list[UUID] = Field(default_factory=list)
    """Файлы, которые сразу кладутся в папку."""
    video_ids: list[UUID] = Field(default_factory=list)
    """Видео, которые сразу кладутся в папку."""
    audio_ids: list[UUID] = Field(default_factory=list)
    """Аудио, которые сразу кладутся в папку."""


class FolderCreateInternalSchema(CloudManagerBaseModel):
    """Данные папки, которые реально пишутся в таблицу: владельца считает репозиторий."""

    name: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None
    is_root: bool = False
    """Корневая папка пользователя: создаётся при регистрации, вручную — нельзя."""


class FolderUpdateSchema(CloudManagerBaseModel):
    """Изменяемые поля папки: всё необязательно.

    `parent_id: null` возвращает папку в корневую папку пользователя,
    отсутствие поля — не меняет родителя.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: UUID | None = None
    file_ids: list[UUID] | None = None
    """Полный новый набор файлов папки: отсутствие поля — не меняет связи."""
    video_ids: list[UUID] | None = None
    """Полный новый набор видео папки: отсутствие поля — не меняет связи."""
    audio_ids: list[UUID] | None = None
    """Полный новый набор аудио папки: отсутствие поля — не меняет связи."""


class FolderFilterSchema(CloudManagerBaseModel):
    """Фильтры списка папок."""

    name: str | None = Field(default=None, max_length=255)
    parent_id: UUID | None = None
    """Показать содержимое конкретной папки."""
    root_only: bool = False
    """Показать только папки верхнего уровня."""
    creator_id: UUID | None = None
    """Папки конкретного пользователя: доступно только админу, остальным — свои."""


class FolderShortSchema(CloudManagerBaseModel):
    """Краткое представление папки — для вложенного списка подпапок."""

    id: UUID
    name: str
    parent_id: UUID | None = None
    created_at: datetime


class FolderResponseSchema(CloudManagerBaseModel):
    """Публичное представление папки вместе с её файлами, видео, аудио и подпапками."""

    id: UUID
    name: str
    parent_id: UUID | None = None
    is_root: bool = False
    """Корневая папка пользователя: единственная точка входа в его дерево."""
    created_at: datetime
    files: list[FileShortSchema] = Field(default_factory=list)
    videos: list[VideoShortSchema] = Field(default_factory=list)
    audios: list[AudioShortSchema] = Field(default_factory=list)
    children: list[FolderShortSchema] = Field(default_factory=list)
