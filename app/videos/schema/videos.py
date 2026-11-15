from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.enums import EVideoType
from app.core.schemes.base import CloudManagerBaseModel


class VideoCreateSchema(CloudManagerBaseModel):
    """Данные видео, которые сохраняются после загрузки объекта в хранилище."""

    name: str = Field(min_length=1, max_length=255)
    object_key: str = Field(max_length=255)
    type: EVideoType
    size: int = Field(ge=0)


class VideoFilterSchema(CloudManagerBaseModel):
    """Фильтры списка видео."""

    name: str | None = Field(default=None, max_length=255)
    types: list[EVideoType] = Field(default_factory=list)
    """Типы видео: пустой список — без фильтра, иначе любое из перечисленных."""


class VideoTypeSchema(CloudManagerBaseModel):
    """Описание разрешённого типа видео — справочник для фронтенда."""

    value: EVideoType
    """Значение для фильтра `?type=` и расширение файла."""
    content_type: str
    """MIME-тип, с которым видео отдаётся браузеру."""


class VideoResponseSchema(CloudManagerBaseModel):
    """Публичное представление видео."""

    id: UUID
    name: str
    object_key: str
    type: EVideoType
    size: int
    created_at: datetime


class VideoShortSchema(CloudManagerBaseModel):
    """Краткое представление видео — для содержимого папки.

    Ключ объекта нужен только видео-модулю: видео адресуется по id,
    а `created_at` показывает в интерфейсе дату загрузки.
    """

    id: UUID
    name: str
    type: EVideoType
    size: int
    created_at: datetime


class VideoPlaybackSchema(CloudManagerBaseModel):
    """Presigned-ссылка на воспроизведение видео."""

    url: str
    content_type: str
    expires_at: datetime
    expires_in: int
