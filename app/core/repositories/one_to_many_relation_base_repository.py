from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import literal_column
from sqlalchemy.sql.base import ExecutableOption

from app.core.context import Context
from app.core.exceptions import ObjectNotFoundException
from app.core.models.base import Base
from app.core.repositories.soft_base_repository import SoftBaseRepository


class OneToManyRelationBaseRepository(SoftBaseRepository):
    def __init__(
        self,
        model_class: type[Base],
        main_entity_column: str,
        dependent_entity_column: str,
        transaction,
        context: Context,
    ):
        super().__init__(model_class=model_class, transaction=transaction, context=context)
        self.main_entity_column: str = main_entity_column
        self.dependent_entity_column: str = dependent_entity_column

    def _split_entity_data(
        self, existing_values: list[dict[str, Any]], new_values: list[dict[str, Any]]
    ) -> dict[str, set[UUID] | list[dict[str, Any]]]:
        existing_ids = {
            value[self.dependent_entity_column]
            for value in existing_values
            if value.get(self.dependent_entity_column)
        }
        new_ids = {
            value[self.dependent_entity_column]
            for value in new_values
            if value.get(self.dependent_entity_column)
        }
        update_ids = new_ids.intersection(existing_ids)
        list_to_create = [
            value
            for value in new_values
            if value.get(self.dependent_entity_column) not in update_ids
        ]
        existing_values_to_update = {
            value.pop(self.dependent_entity_column): value
            for value in existing_values
            if value.get(self.dependent_entity_column) in update_ids
        }
        new_values_to_update = {
            value.pop(self.dependent_entity_column): value
            for value in new_values
            if value.get(self.dependent_entity_column) in update_ids
        }
        list_to_update = []
        for item_id, item_value in new_values_to_update.items():
            old_value = existing_values_to_update[item_id]
            new_value = {k: v for k, v in item_value.items() if v != old_value[k]}
            if new_value:
                list_to_update.append({self.dependent_entity_column: item_id, **dict(new_value)})
        id_set_to_delete = set(existing_ids).difference(new_ids)
        return {
            'list_to_create': list_to_create,
            'list_to_update': list_to_update,
            'id_set_to_delete': id_set_to_delete,
        }

    async def _update_relation(
        self, *, main_entity_id: UUID, schema: type[BaseModel], new_values: list[dict[str, Any]]
    ) -> None:
        existing_dependent_entity_list = await self._get_dependent_entity_list(
            main_entity_id=main_entity_id, schema=schema
        )
        existing_values = [value.model_dump() for value in existing_dependent_entity_list]
        relations_data = self._split_entity_data(
            existing_values=existing_values, new_values=new_values
        )
        if relations_data['list_to_create']:
            await self._create_relation_with_data(
                main_entity_id=main_entity_id, relation_data=relations_data['list_to_create']
            )
        if relations_data['list_to_update']:
            for item in relations_data['list_to_update']:
                await self._update_one_relation(main_entity_id=main_entity_id, relation_data=item)
        if relations_data['id_set_to_delete']:
            await self._delete_relation(
                main_entity_id=main_entity_id,
                dependent_entity_set=relations_data['id_set_to_delete'],
            )

    async def _create_relation(
        self, *, main_entity_id: UUID, dependent_entity_set: set[UUID]
    ) -> None:
        values = [
            {self.dependent_entity_column: dependent_entity_id}
            for dependent_entity_id in dependent_entity_set
        ]
        await self._create_relation_with_data(main_entity_id=main_entity_id, relation_data=values)

    async def create_relation(
        self, main_entity_id: UUID, *, dependent_entity_set: set[UUID]
    ) -> None:
        await self._create_relation(
            main_entity_id=main_entity_id, dependent_entity_set=dependent_entity_set
        )

    async def _create_relation_with_data(
        self, *, main_entity_id: UUID, relation_data: list[dict[str, Any]]
    ) -> None:
        values = [{self.main_entity_column: main_entity_id, **item} for item in relation_data]
        await self._create_many(values=values)

    async def _update_one_relation(
        self, *, main_entity_id: UUID, relation_data: dict[str, Any]
    ) -> None:
        where_args = (
            literal_column(self.main_entity_column) == main_entity_id,
            literal_column(self.dependent_entity_column)
            == relation_data.get(self.dependent_entity_column),
        )
        await self._update_many(relation_data, *where_args)

    async def _get_dependent_entity_list(
        self,
        *,
        main_entity_id: UUID,
        schema: type[BaseModel] | None = None,
        filter_by: dict | None = None,
        columns: tuple | None = None,
        options: list[ExecutableOption] | None = None,
    ) -> list:
        if filter_by is None:
            filter_by = {}
        return await self._get_list(
            columns=columns,
            schema=schema,
            filter_by={self.main_entity_column: main_entity_id, **filter_by},
            options=options,
            scalars=True,
        )

    async def _delete_relation(
        self, *, main_entity_id: UUID, dependent_entity_set: set[UUID] | None = None
    ) -> UUID:
        args = [literal_column(self.main_entity_column) == main_entity_id]
        if dependent_entity_set is not None:
            args.append(literal_column(self.dependent_entity_column).in_(dependent_entity_set))
        pks = await self._get_list(*args, columns=(self._model_class.id,), scalars=True)
        return await self._delete_many(list(pks or []))

    async def delete_relation(
        self, main_entity_id: UUID, *, dependent_entity_set: set[UUID] | None = None
    ) -> UUID:
        return await self._delete_relation(
            main_entity_id=main_entity_id, dependent_entity_set=dependent_entity_set
        )

    async def _get_main_entity_id(self, *, dependent_entity_id: UUID) -> UUID:
        columns = (literal_column(self.main_entity_column),)
        query = self._get_query(columns).where(
            literal_column(self.dependent_entity_column) == dependent_entity_id
        )
        result = await self.transaction.select_one(query, scalars=True)
        if result:
            return result
        else:
            raise ObjectNotFoundException(
                object_id=dependent_entity_id, object_class=self._model_class
            )
