from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

from app.core.enums import PAGE_LIMIT


@dataclass
class Paginator:
    """Параметры постраничной выдачи."""

    page: int
    page_size: int


def get_paginator(
    page: Annotated[int, Query(ge=1, description='Номер страницы')] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_LIMIT, description='Размер страницы')] = 25,
) -> Paginator:
    """Собирает пагинацию из query-параметров запроса."""
    return Paginator(page=page, page_size=page_size)


PaginatorDep = Annotated[Paginator, Depends(get_paginator)]
