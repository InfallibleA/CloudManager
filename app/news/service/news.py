from uuid import UUID

from app.core.dependencies import Paginator
from app.core.exceptions import ValidationException
from app.core.schemes import PaginatedSchema
from app.files.constants import IMAGE_TYPES_HINT, is_image_type
from app.files.service.files import FilesService
from app.news.repository.news import NewsRepository
from app.news.schema.news import (
    NewsCreateSchema,
    NewsFilterSchema,
    NewsResponseSchema,
    NewsUpdateSchema,
)


class NewsService:
    """Создание, изменение и выдача новостей вместе с их файлами."""

    def __init__(self, *, news_repository: NewsRepository, files_service: FilesService):
        self._news_repository = news_repository
        self._files_service = files_service

    async def create(self, *, data: NewsCreateSchema) -> NewsResponseSchema:
        await self._validate_media(media_id=data.media_id)
        return await self._news_repository.create_one(data=data)

    async def get_one(self, *, pk: UUID) -> NewsResponseSchema:
        return await self._news_repository.get_one(pk=pk)

    async def get_list(
        self, *, filters: NewsFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[NewsResponseSchema]:
        return await self._news_repository.get_list(filters=filters, paginator=paginator)

    async def update(self, *, pk: UUID, data: NewsUpdateSchema) -> NewsResponseSchema:
        await self._news_repository.has_one(pk, raise_error=True)
        if data.media_id is not None:
            await self._validate_media(media_id=data.media_id)
        if data.weight is not None:
            await self._validate_weight(weight=data.weight)
        return await self._news_repository.update_one(pk=pk, data=data)

    async def delete(self, *, pk: UUID) -> None:
        await self._news_repository.delete_one(pk=pk)

    async def _validate_media(self, *, media_id: UUID | None) -> None:
        """Проверяет, что media_id — существующий файл-изображение.

        Главное изображение новости должно лежать в files и быть картинкой:
        документы в витрине показать нельзя, им место в списке файлов новости.
        """
        if media_id is None:
            return

        found = await self._files_service.get_many(pks=[media_id])
        file = found[0] if found else None
        if file is None:
            raise ValidationException(detail=f'Файл не найден: {media_id}.')
        if not is_image_type(file.type):
            raise ValidationException(
                detail=(
                    f'media_id должен указывать на изображение. '
                    f'Разрешены: {IMAGE_TYPES_HINT}.'
                )
            )

    async def _validate_weight(self, *, weight: int) -> None:
        """Проверяет, что вес не выходит за пределы списка: допустимы позиции 0..N-1."""
        max_weight = await self._news_repository.get_max_weight()
        if weight > max_weight:
            raise ValidationException(
                detail=f'Вес не может быть больше {max_weight}: позиции в списке идут подряд.'
            )
