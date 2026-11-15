from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.enums import EFileType
from app.core.schemes.base import CloudManagerBaseModel


class FileCreateSchema(CloudManagerBaseModel):
    """Данные файла, которые сохраняются после загрузки объекта в хранилище."""

    name: str = Field(min_length=1, max_length=255)
    object_key: str = Field(max_length=255)
    type: EFileType
    size: int = Field(ge=0)


class FileUpdateSchema(CloudManagerBaseModel):
    """Изменяемые поля файла: переименование не трогает сам объект в хранилище."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class FileFilterSchema(CloudManagerBaseModel):
    """Фильтры списка файлов."""

    name: str | None = Field(default=None, max_length=255)
    types: list[EFileType] = Field(default_factory=list)
    """Типы файлов: пустой список — без фильтра, иначе любое из перечисленных."""
    creator_id: UUID | None = None
    """Файлы конкретного пользователя: id его аккаунта."""


class FileTypeSchema(CloudManagerBaseModel):
    """Описание разрешённого типа файла — справочник для фронтенда."""

    value: EFileType
    """Значение для фильтра `?type=` и расширение файла."""
    content_type: str
    """MIME-тип, с которым файл отдаётся клиенту."""
    is_image: bool
    """Можно ли показывать файл в `<img>` и отдавать инлайном."""


class FileResponseSchema(CloudManagerBaseModel):
    """Публичное представление файла."""

    id: UUID
    name: str
    object_key: str
    type: EFileType
    size: int
    creator_id: UUID | None = None
    """Владелец файла: id аккаунта, загрузившего файл."""
    creator_login: str | None = None
    """Логин владельца: готовое значение для колонки «Пользователь»."""
    created_at: datetime


class FileShortSchema(CloudManagerBaseModel):
    """Краткое представление файла — для вложений в другие сущности.

    Ключ объекта нужен только файловому модулю: файл доступен по id,
    а `created_at` показывает в интерфейсе дату загрузки.
    """

    id: UUID
    name: str
    type: EFileType
    size: int
    created_at: datetime
