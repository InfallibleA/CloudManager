from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.enums import EAudioType
from app.core.schemes.base import CloudManagerBaseModel


class AudioCreateSchema(CloudManagerBaseModel):
    """Данные аудио, которые сохраняются после загрузки объекта в хранилище."""

    name: str = Field(min_length=1, max_length=255)
    object_key: str = Field(max_length=255)
    type: EAudioType
    size: int = Field(ge=0)


class AudioUpdateSchema(CloudManagerBaseModel):
    """Изменяемые поля аудио: переименование не трогает сам объект в хранилище."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class AudioFilterSchema(CloudManagerBaseModel):
    """Фильтры списка аудио."""

    name: str | None = Field(default=None, max_length=255)
    types: list[EAudioType] = Field(default_factory=list)
    """Типы аудио: пустой список — без фильтра, иначе любое из перечисленных."""


class AudioTypeSchema(CloudManagerBaseModel):
    """Описание разрешённого типа аудио — справочник для фронтенда."""

    value: EAudioType
    """Значение для фильтра `?type=` и расширение файла."""
    content_type: str
    """MIME-тип, с которым аудио отдаётся браузеру."""


class AudioResponseSchema(CloudManagerBaseModel):
    """Публичное представление аудио."""

    id: UUID
    name: str
    object_key: str
    type: EAudioType
    size: int
    created_at: datetime


class AudioShortSchema(CloudManagerBaseModel):
    """Краткое представление аудио — для содержимого папки."""

    id: UUID
    name: str
    type: EAudioType
    size: int
    created_at: datetime


class AudioPlaybackSchema(CloudManagerBaseModel):
    """Presigned-ссылка на воспроизведение аудио."""

    url: str
    content_type: str
    expires_at: datetime
    expires_in: int
