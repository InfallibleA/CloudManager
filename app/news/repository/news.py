from uuid import UUID

from sqlalchemy import func, select, update

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.exceptions import ObjectNotFoundException
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.news.model.news import News
from app.news.schema.news import (
    NewsCreateInternalSchema,
    NewsCreateSchema,
    NewsFilterSchema,
    NewsResponseSchema,
    NewsUpdateSchema,
)


class NewsRepository(SoftBaseRepository):
    def __init__(self, transaction: Transaction, context: Context):
        super().__init__(model_class=News, transaction=transaction, context=context)

    async def create_one(self, *, data: NewsCreateSchema) -> NewsResponseSchema:
        """Создаёт новость и ставит её в конец списка (последний вес + 1)."""
        internal = NewsCreateInternalSchema(
            name=data.name,
            description=data.description,
            weight=await self._next_weight(),
            media_id=data.media_id,
        )
        return await self._create_one(internal, NewsResponseSchema)

    async def get_one(self, *, pk: UUID) -> NewsResponseSchema:
        return await self._get_one(pk, NewsResponseSchema, scalars=True)

    async def get_list(
        self, *, filters: NewsFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[NewsResponseSchema]:
        """Постраничный список неудалённых новостей в порядке возрастания веса."""
        db_model = self._model_class
        conditions = []
        if filters.name:
            conditions.append(db_model.name.ilike(f'%{filters.name}%'))
        if filters.weight_from is not None:
            conditions.append(db_model.weight >= filters.weight_from)
        if filters.weight_to is not None:
            conditions.append(db_model.weight <= filters.weight_to)

        page = await self._get_list(
            *conditions,
            schema=NewsResponseSchema,
            scalars=True,
            paginator=paginator,
            transform_query=lambda query: query.order_by(db_model.weight),
        )
        return page

    async def update_one(self, *, pk: UUID, data: NewsUpdateSchema) -> NewsResponseSchema:
        """Обновляет новость; при перестановке по весу остальные записи сдвигаются."""
        await self.has_one(pk, raise_error=True)
        values = data.model_dump(exclude={'weight'}, exclude_unset=True)

        async with self.transaction.atomic():
            if values:
                await self._update_one(pk, values, NewsResponseSchema)
            if data.weight is not None:
                await self._move_to_weight(pk=pk, weight=data.weight)

        return await self.get_one(pk=pk)

    async def delete_one(self, *, pk: UUID) -> None:
        """Мягко удаляет новость, убирает её связи с файлами и смыкает веса."""
        await self.delete_many(pks=[pk])

    async def delete_many(self, *, pks: list[UUID]) -> None:
        """Мягко удаляет новости, убирает связи с файлами и пересчитывает веса."""
        if not pks:
            return

        db_model = self._model_class
        found = await self._get_list(
            db_model.id.in_(pks), columns=(db_model.id,), scalars=True
        )
        found_ids = set(found or [])
        for pk in pks:
            if pk not in found_ids:
                raise ObjectNotFoundException(object_id=pk, object_class=db_model)

        async with self.transaction.atomic():
            await self._delete_many(list(found_ids))
            await self._recount_weights()

    async def _recount_weights(self) -> None:
        """Пересчитывает веса оставшихся новостей в 0..N-1, сохраняя прежний порядок."""
        db_model = self._model_class
        order = (db_model.weight, db_model.created_at)
        next_weight = func.row_number().over(order_by=order) - 1
        numbered = (
            select(db_model.id.label('id'), next_weight.label('weight'))
            .where(db_model.deleted_id.is_(None))
            .subquery()
        )
        query = (
            update(db_model)
            .where(db_model.id == numbered.c.id, db_model.weight != numbered.c.weight)
            .values(weight=numbered.c.weight)
        )
        await self.transaction.execute(query)

    async def get_max_weight(self) -> int:
        """Максимальный вес неудалённых новостей: -1, если новостей нет."""
        query = select(func.coalesce(func.max(self._model_class.weight), -1))
        result = await self.transaction.execute(query)
        return result.scalar_one()

    async def _next_weight(self) -> int:
        """Вес новой новости: следующий за максимальным (0 для первой)."""
        return await self.get_max_weight() + 1

    async def _move_to_weight(self, *, pk: UUID, weight: int) -> None:
        """Переставляет новость на вес `weight`, не оставляя пропуска на прежнем месте."""
        db_model = self._model_class
        old_weight = (
            await self.transaction.execute(select(db_model.weight).where(db_model.id == pk))
        ).scalar_one()
        if old_weight == weight:
            return

        # 1. убираем новость из последовательности — все, кто ниже, смыкаются вверх
        await self.transaction.execute(
            self._filter_query(
                update(db_model)
                .where(db_model.id != pk, db_model.weight > old_weight)
                .values(weight=db_model.weight - 1)
            )
        )
        # 2. освобождаем место под новую позицию
        await self.transaction.execute(
            self._filter_query(
                update(db_model)
                .where(db_model.id != pk, db_model.weight >= weight)
                .values(weight=db_model.weight + 1)
            )
        )
        await self.transaction.execute(
            update(db_model).where(db_model.id == pk).values(weight=weight)
        )
