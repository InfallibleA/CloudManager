from uuid import UUID

from sqlalchemy import update

from app.core.context import Context
from app.core.engines.database import Transaction
from app.core.models.base import Base
from app.core.repositories.base_repository import BaseRepository
from app.core.utils.db import atomic_delete
from app.core.utils.pget import pget


class SoftBaseRepository(BaseRepository):
    def __init__(self, model_class: type[Base], transaction: Transaction, context: Context):
        super().__init__(model_class=model_class, transaction=transaction, context=context)

    def _filter_query(self, q, use_deleted: bool = False):
        if use_deleted:
            return q
        else:
            return q.where(self._model_class.deleted_id.is_(None))

    async def _delete_one(self, pk: UUID) -> UUID | None:
        await self.has_one(pk, raise_error=True)
        return await self._delete_many([pk])

    async def _delete_many(self, pks: list[UUID]) -> UUID | None:
        """Мягко удаляет записи по списку id: все они помечаются одной записью SoftDel."""
        if not pks:
            return None

        db_model = self._model_class
        async with atomic_delete(
            self.transaction, creator_id=pget(self.context, 'user.id')
        ) as delete_transaction_id:
            change_del_status_query = (
                update(db_model)
                .values(deleted_id=delete_transaction_id)
                .where(db_model.id.in_(pks), db_model.deleted_id.is_(None))
            )
            await self.transaction.execute(change_del_status_query)
            return delete_transaction_id
