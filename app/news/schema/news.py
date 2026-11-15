from uuid import UUID

from pydantic import Field

from app.core.schemes.base import CloudManagerBaseModel


class NewsCreateSchema(CloudManagerBaseModel):
    """Данные для создания новости."""

    name: str = Field(min_length=1, max_length=255)
    description: str = ''
    media_id: UUID | None = None
    """Главное изображение новости: id файла-картинки. Необязательно."""


class NewsCreateInternalSchema(CloudManagerBaseModel):
    """Данные новости, которые реально пишутся в таблицу: вес считает репозиторий."""

    name: str = Field(min_length=1, max_length=255)
    description: str = ''
    weight: int = Field(ge=0)
    media_id: UUID | None = None


class NewsUpdateSchema(CloudManagerBaseModel):
    """Изменяемые поля новости: всё необязательно."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    weight: int | None = Field(default=None, ge=0)
    media_id: UUID | None = None
    """Главное изображение новости: id файла-картинки. Необязательно."""


class NewsFilterSchema(CloudManagerBaseModel):
    """Фильтры списка новостей."""

    name: str | None = Field(default=None, max_length=255)
    weight_from: int | None = Field(default=None, ge=0)
    weight_to: int | None = Field(default=None, ge=0)


class NewsResponseSchema(CloudManagerBaseModel):
    """Публичное представление новости."""

    id: UUID
    name: str
    description: str
    weight: int
    media_id: UUID | None = None
    """Главное изображение новости: id файла-картинки. Может отсутствовать."""
