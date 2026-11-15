from uuid import UUID

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.exceptions import ObjectNotFoundException
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.videos.model.video import Video
from app.videos.schema.videos import VideoCreateSchema, VideoFilterSchema, VideoResponseSchema


class VideosRepository(SoftBaseRepository):
    def __init__(self, transaction: Transaction, context: Context):
        super().__init__(model_class=Video, transaction=transaction, context=context)

    async def create_one(self, *, data: VideoCreateSchema) -> VideoResponseSchema:
        """Сохраняет запись о видео, уже загруженном в хранилище."""
        return await self._create_one(data, VideoResponseSchema)

    async def get_one(self, *, pk: UUID) -> VideoResponseSchema:
        return await self._get_one(pk, VideoResponseSchema, scalars=True)

    async def get_one_by_name(self, *, name: str) -> VideoResponseSchema:
        """Находит видео по точному имени; не найдено — 404."""
        videos = await self._get_list(
            self._model_class.name == name, schema=VideoResponseSchema, scalars=True
        )
        if not videos:
            raise ObjectNotFoundException(detail=f'Видео с именем «{name}» не найдено.')
        return videos[0]

    async def exists_by_name(self, *, name: str) -> bool:
        """Проверяет, занято ли имя активным (неудалённым) видео."""
        return await self._exists(self._model_class.name == name)

    async def get_list(
        self, *, filters: VideoFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[VideoResponseSchema]:
        """Постраничный список неудалённых видео с фильтрами по имени и типу."""
        db_model = self._model_class
        conditions = []
        if filters.name:
            conditions.append(db_model.name.ilike(f'%{filters.name}%'))
        if filters.types:
            conditions.append(db_model.type.in_(filters.types))

        return await self._get_list(
            *conditions,
            schema=VideoResponseSchema,
            scalars=True,
            paginator=paginator,
            transform_query=lambda query: query.order_by(db_model.created_at.desc()),
        )

    async def delete_one(self, *, pk: UUID) -> VideoResponseSchema:
        """Мягко удаляет видео и возвращает его данные для удаления объекта из S3."""
        video = await self._get_one(pk, VideoResponseSchema, scalars=True)
        await self._delete_one(pk)
        return video
