from typing import Generic, TypeVar

from pydantic import BaseModel, Field

ResponseSchema = TypeVar('ResponseSchema')


class PaginatedSchema(BaseModel, Generic[ResponseSchema]):
    count: int
    offset: int
    page: int
    page_size: int
    data: list[ResponseSchema] | None = Field(default=None)
