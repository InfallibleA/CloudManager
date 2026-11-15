from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import (
    Index,
    Select,
    UniqueConstraint,
    and_,
    delete,
    insert,
    inspect,
    literal_column,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.base import ExecutableOption

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.enums import EUser
from app.core.exceptions import (
    BaseOrderException,
    ObjectNotFoundException,
    UniqueConstraintException,
)
from app.core.models.base import Base
from app.core.schemes import BaseSchema, PaginatedSchema
from app.core.utils.pget import pget


class BaseRepository:
    def __init__(self, transaction, model_class: type[Base], context: Context):
        self.transaction = transaction
        self.session = transaction  # todo remove deprecated
        self._model_class = model_class
        self._inspect = inspect(self._model_class)
        self.context = context

    async def _get_one(
            self,
            pk: UUID,
            schema: type[BaseModel],
            columns: tuple | None = None,
            *,
            options: list[ExecutableOption] | None = None,
            scalars: bool = False,
            use_deleted: bool = False,
    ):
        result = await self._get_one_or_none(
            pk, schema, columns, options=options, scalars=scalars, use_deleted=use_deleted
        )
        if not result:
            raise ObjectNotFoundException(object_id=pk, object_class=self._model_class)
        return result

    async def _get_one_or_none(
            self,
            pk: UUID,
            schema: type[BaseModel],
            columns: tuple | None = None,
            *,
            options: list[ExecutableOption] | None = None,
            scalars: bool = False,
            use_deleted: bool = False,
    ):
        db_model = self._model_class
        query = self._get_query(columns, use_deleted)
        query = query.where(db_model.id == pk)
        if options:
            for opt in options:
                query = query.options(opt)
        if scalars:
            result = await self.session.scalars(query)
            return schema.model_validate(result[0], from_attributes=True) if result else None
        else:
            result = await self.session.select_one(query)
            return schema.model_validate(result, from_attributes=True) if result else None

    async def _get_list(
            self,
            *where_args,
            schema: type[BaseModel] | None = None,
            columns: tuple | None = None,
            options: list[ExecutableOption] | None = None,
            scalars: bool = False,
            paginator: Paginator | None = None,
            filter_by: dict | None = None,
            transform_query: Callable[[Select], Select] | None = None,
            distinct: bool = False,
            asdict: bool = False,
    ):
        query = self._get_query(columns)
        if where_args:
            query = query.where(*where_args)
        if transform_query:
            query = transform_query(query)
        if options:
            for opt in options:
                query = query.options(opt)
        if filter_by:
            query = query.filter_by(**filter_by)
        if distinct:
            query = query.distinct()

        if paginator:
            # вычисляем count до модификации query
            count = await self.session.count(query)
            page, page_size = paginator.page, paginator.page_size
            query = query.slice(page * page_size - page_size, page * page_size)
            offset = page_size * (page - 1)
        if scalars:
            result = await self.session.scalars(query)
        else:
            result = await self.session.execute(query)
        if schema:
            if asdict:
                result = [r._asdict() for r in result]
            result = (
                [schema.model_validate(_, from_attributes=True) for _ in result] if result else []
            )
        if paginator:
            return PaginatedSchema(
                count=count,
                offset=offset,
                page=paginator.page,
                page_size=paginator.page_size,
                data=result,
            )
        return result

    async def _create_one(
        self,
        data: BaseModel,
        schema: type[BaseModel],
        on_conflict_do_update: bool = False,
        creator_id: UUID | None = None,
    ):
        await self._validate(data)

        db_model = self._model_class
        values = data.model_dump()
        values['creator_id'] = self._resolve_creator_id(creator_id)

        query = insert(db_model).values(values).returning(literal_column('*'))
        if on_conflict_do_update:
            values['deleted_id'] = None
            query = query.on_conflict_do_update(index_elements=[db_model.id], set_=values)
        result = await self.session.execute(query)
        if not result:
            raise BaseOrderException
        return schema.model_validate(result.first(), from_attributes=True)

    async def _create_many(
        self, values: list[dict[str, Any]], conflict: bool = False, creator_id: UUID | None = None
    ):
        for value in values:
            value['creator_id'] = self._resolve_creator_id(creator_id)
            await self._validate(value)
        db_model = self._model_class
        query = insert(db_model).values(values)
        if conflict:
            set_dict = {key: getattr(query.excluded, key) for key in values[0].keys()}
            query = query.on_conflict_do_update(
                index_elements=[db_model.id],  # поля, которые являются уникальными ключами
                set_=set_dict,
            )
        await self.session.execute(query)

    async def _update_one(
            self, pk: UUID, data: BaseModel | dict, schema: type[BaseModel] | None = None
    ):
        await self.has_one(pk, raise_error=True)
        await self._validate(data, pk)
        db_model = self._model_class
        # exclude_unset — чтобы PATCH не затирал поля, которых нет в запросе
        values = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        query = (
            update(db_model)
            .values(values)
            .where(db_model.id == pk)
            .returning(*db_model.__mapper__.columns)
        )
        query = self._filter_query(query)
        result = await self.session.execute(query)
        if not result:
            raise ObjectNotFoundException(object_id=pk, object_class=db_model)
        if schema:
            result = schema.model_validate(result.first(), from_attributes=True)
        return result

    async def _update_many(self, values: dict, *where_args):
        db_model = self._model_class
        query = update(db_model).values(values).where(*where_args)
        query = self._filter_query(query)
        await self.session.execute(query)

    async def _delete_one(self, pk: UUID):
        await self.has_one(pk, raise_error=True)
        await self._delete_many([pk])

    async def _delete_many(self, pks: list[UUID]):
        """Жёстко удаляет записи по списку id."""
        if not pks:
            return

        db_model = self._model_class
        await self.session.execute(delete(db_model).where(db_model.id.in_(pks)))

    def _filter_query(self, query, use_deleted: bool = False):
        return query

    def _get_query(self, columns=None, use_deleted: bool = False):
        q = select(*columns) if columns else select(self._model_class)
        return self._filter_query(q, use_deleted=use_deleted)

    async def has_one(self, pk: UUID, raise_error: bool = False) -> bool:
        """Проверяет, что объект существует; при raise_error бросает 404."""
        db_model = self._model_class
        query = self._get_query().where(db_model.id == pk)
        res = await self.session.select_one(query, scalars=True)
        if raise_error and not res:
            raise ObjectNotFoundException(object_id=pk, object_class=db_model)
        return bool(res)

    async def _exists(self, *where_args) -> bool:
        """Проверяет, что по условиям есть хотя бы одна запись."""
        query = self._get_query().where(*where_args)
        return await self.session.is_exists(query)

    def _resolve_creator_id(self, creator_id: UUID | None = None) -> UUID:
        """Кто создаёт запись: явный creator_id, текущий пользователь или ROOT_USER."""
        return creator_id or pget(self.context, 'user.id') or EUser.ROOT_USER.value

    async def _validate(self, schema: BaseModel | dict, object_id: UUID | None = None):
        if isinstance(schema, BaseSchema):
            await schema.async_validate(session=self.transaction, object_id=object_id)
        await self.validate_uniqueness(schema, object_id)

    async def validate_uniqueness(self, input_data: BaseModel | dict, obj_id: UUID | None = None):
        def get_index_constraint_conditions(data: BaseModel | dict):
            data = data.model_dump() if isinstance(data, BaseModel) else data
            constraints_and_indexes = [
                inst
                for inst in [
                    *(self._model_class.__table__.constraints),
                    *(self._model_class.__table__.indexes),
                ]
                if isinstance(inst, UniqueConstraint) or (isinstance(inst, Index) and inst.unique)
            ]

            conditions = []
            for inst in constraints_and_indexes:
                postgresql_where = inst.dialect_kwargs.get('postgresql_where')
                conditions.append(
                    and_(*(map_column == data.get(map_column.name) for map_column in inst.columns))
                    if postgresql_where is None
                    else and_(
                        and_(
                            *(
                                map_column == data.get(map_column.name)
                                for map_column in inst.columns
                            )
                        ),
                        postgresql_where,
                    )
                )

            return conditions

        query = select(self._model_class)

        if obj_id:
            query = query.where(self._model_class.id != obj_id)
        constraints = get_index_constraint_conditions(input_data)

        result = None
        if constraints:
            query = query.where(or_(*constraints))
            result = await self.session.scalars(query)

        if result:
            raise UniqueConstraintException()
