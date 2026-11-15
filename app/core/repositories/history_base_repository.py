from pydantic import BaseModel
from sqlalchemy.sql.base import ExecutableOption

from app.core.context import Context
from app.core.models.base import Base
from app.core.repositories.soft_base_repository import SoftBaseRepository


class HistoryBaseRepository(SoftBaseRepository):
    def __init__(self, model_class: type[Base], transaction, context: Context):
        super().__init__(model_class=model_class, transaction=transaction, context=context)

    async def _get_last_entry(
        self, *args, options: list[ExecutableOption] = (), schema: type[BaseModel] | None = None
    ):
        query = (
            self._get_query().where(*args).order_by(self._model_class.created_at.desc()).limit(1)
        )
        for opt in options:
            query = query.options(opt)
        result = await self.transaction.select_one(query, scalars=True)
        if schema and result:
            return schema.model_validate(result, from_attributes=True)
        return result

    async def _set_entry(self, data: BaseModel, schema: type[BaseModel]):
        await self._create_one(data=data, schema=schema)
