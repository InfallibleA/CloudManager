from uuid import UUID

from sqlalchemy import delete, select

from app.audios.model.audio import Audio
from app.audios.schema.audios import (
    AudioCreateSchema,
    AudioFilterSchema,
    AudioResponseSchema,
    AudioUpdateSchema,
)
from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.exceptions import ObjectNotFoundException
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.folders.model.folder_audio import folder_audios


class AudiosRepository(SoftBaseRepository):
    def __init__(self, transaction: Transaction, context: Context):
        super().__init__(model_class=Audio, transaction=transaction, context=context)

    async def create_one(self, *, data: AudioCreateSchema) -> AudioResponseSchema:
        """Сохраняет запись об аудио, уже загруженном в хранилище."""
        return await self._create_one(data, AudioResponseSchema)

    async def get_one(self, *, pk: UUID) -> AudioResponseSchema:
        return await self._get_one(pk, AudioResponseSchema, scalars=True)

    async def get_one_by_name(self, *, name: str) -> AudioResponseSchema:
        """Находит аудио по точному имени; не найдено — 404."""
        audios = await self._get_list(
            self._model_class.name == name, schema=AudioResponseSchema, scalars=True
        )
        if not audios:
            raise ObjectNotFoundException(detail=f'Аудио с именем «{name}» не найдено.')
        return audios[0]

    async def exists_by_name(self, *, name: str, exclude_id: UUID | None = None) -> bool:
        """Проверяет, занято ли имя активным (неудалённым) аудио."""
        conditions = [self._model_class.name == name]
        if exclude_id is not None:
            conditions.append(self._model_class.id != exclude_id)
        return await self._exists(*conditions)

    async def get_list(
        self, *, filters: AudioFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[AudioResponseSchema]:
        """Постраничный список неудалённых аудио с фильтрами по имени и типу."""
        db_model = self._model_class
        conditions = []
        if filters.name:
            conditions.append(db_model.name.ilike(f'%{filters.name}%'))
        if filters.types:
            conditions.append(db_model.type.in_(filters.types))

        return await self._get_list(
            *conditions,
            schema=AudioResponseSchema,
            scalars=True,
            paginator=paginator,
            transform_query=lambda query: query.order_by(db_model.created_at.desc()),
        )

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        """id создателя аудио: по нему проверяется право на изменение и удаление.

        Неудалённого аудио нет — 404, как и при удалении.
        """
        db_model = self._model_class
        query = select(db_model.creator_id).where(db_model.id == pk, db_model.deleted_id.is_(None))
        creator_id = (await self.transaction.execute(query)).scalar_one_or_none()
        if creator_id is None:
            raise ObjectNotFoundException(object_id=pk, object_class=db_model)
        return creator_id

    async def get_many(self, *, pks: list[UUID]) -> list[AudioResponseSchema]:
        """Возвращает неудалённые аудио по списку id (для связей и проверок)."""
        if not pks:
            return []

        return await self._get_list(
            self._model_class.id.in_(pks), schema=AudioResponseSchema, scalars=True
        )

    async def update_one(self, *, pk: UUID, data: AudioUpdateSchema) -> AudioResponseSchema:
        """Меняет имя аудио; пустой патч просто возвращает текущую запись.

        Ключ объекта, тип и размер не меняются: файл в хранилище остаётся тем же.
        """
        if data.name is None:
            return await self.get_one(pk=pk)
        return await self._update_one(pk, data, AudioResponseSchema)

    async def delete_one(self, *, pk: UUID) -> AudioResponseSchema:
        """Мягко удаляет аудио и возвращает его данные для удаления объекта из S3."""
        audios = await self.delete_many(pks=[pk])
        return audios[0]

    async def delete_many(self, *, pks: list[UUID]) -> list[AudioResponseSchema]:
        """Мягко удаляет аудио, убирает их связи с папками и возвращает записи."""
        if not pks:
            return []

        audios = await self.get_many(pks=pks)
        found_ids = {audio.id for audio in audios}
        for pk in pks:
            if pk not in found_ids:
                raise ObjectNotFoundException(object_id=pk, object_class=self._model_class)

        async with self.transaction.atomic():
            await self._unlink_folders(pks=list(found_ids))
            await self._delete_many(list(found_ids))

        return audios

    async def _unlink_folders(self, *, pks: list[UUID]) -> None:
        """Убирает аудио из папок (таблица folder_audios)."""
        await self.transaction.execute(
            delete(folder_audios).where(folder_audios.c.audio_id.in_(pks))
        )
