from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from sqlalchemy import insert

from app.core.enums import EUser
from app.core.models.soft_del import SoftDel


@asynccontextmanager
async def atomic_delete(transaction, *, creator_id: UUID | None = None):
    """Помечает удаление: создаёт запись SoftDel и передаёт её id вызывающему.

    creator_id — кто удаляет: пользователь из контекста, либо ROOT_USER для служебных сценариев.
    """
    delete_transaction_id = getattr(transaction, 'delete_transaction_id', None)
    if delete_transaction_id:
        yield delete_transaction_id
    else:
        try:
            async with transaction.atomic():
                delete_transaction_id = uuid4()
                setattr(transaction, 'delete_transaction_id', delete_transaction_id)
                insert_soft_del_query = insert(SoftDel).values(
                    id=delete_transaction_id,
                    creator_id=creator_id or EUser.ROOT_USER.value,
                )
                await transaction.execute(insert_soft_del_query)
                yield delete_transaction_id
        finally:
            if delete_transaction_id:
                delattr(transaction, 'delete_transaction_id')
