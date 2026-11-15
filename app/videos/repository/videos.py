from uuid import UUID

from sqlalchemy import delete, select

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.exceptions import ObjectNotFoundException
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.folders.model.folder_video import folder_videos
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

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        """id создателя видео: по нему проверяется право на удаление.

        Неудалённого видео нет — 404, как и при удалении.
        """
        db_model = self._model_class
        query = select(db_model.creator_id).where(db_model.id == pk, db_model.deleted_id.is_(None))
        creator_id = (await self.transaction.execute(query)).scalar_one_or_none()
        if creator_id is None:
            raise ObjectNotFoundException(object_id=pk, object_class=db_model)
        return creator_id

    async def get_many(self, *, pks: list[UUID]) -> list[VideoResponseSchema]:
        """Возвращает неудалённые видео по списку id (для связей и проверок)."""
        if not pks:
            return []

        return await self._get_list(
            self._model_class.id.in_(pks), schema=VideoResponseSchema, scalars=True
        )

    async def delete_one(self, *, pk: UUID) -> VideoResponseSchema:
        """Мягко удаляет видео и возвращает его данные для удаления объекта из S3."""
        videos = await self.delete_many(pks=[pk])
        return videos[0]

    async def delete_many(self, *, pks: list[UUID]) -> list[VideoResponseSchema]:
        """Мягко удаляет видео, убирает их связи с папками и возвращает записи.

        Связи из `folder_videos` нельзя удалить каскадом БД, поэтому они убираются
        явно — иначе в таблице останутся «висячие» записи. Возвращённые записи
        нужны сервису, чтобы почистить объекты в S3-хранилище.
        """
        if not pks:
            return []

        videos = await self.get_many(pks=pks)
        found_ids = {video.id for video in videos}
        for pk in pks:
            if pk not in found_ids:
                raise ObjectNotFoundException(object_id=pk, object_class=self._model_class)

        async with self.transaction.atomic():
            await self._unlink_folders(pks=list(found_ids))
            await self._delete_many(list(found_ids))

        return videos

    async def _unlink_folders(self, *, pks: list[UUID]) -> None:
        """Убирает видео из папок (таблица folder_videos)."""
        await self.transaction.execute(
            delete(folder_videos).where(folder_videos.c.video_id.in_(pks))
        )
