from typing import Annotated

from fastapi import Query

from app.news.schema.news import NewsFilterSchema


def get_news_filters(
    name: Annotated[str | None, Query(max_length=255, description='Поиск по названию')] = None,
    weight_from: Annotated[int | None, Query(ge=0, description='Вес от (включительно)')] = None,
    weight_to: Annotated[int | None, Query(ge=0, description='Вес до (включительно)')] = None,
) -> NewsFilterSchema:
    """Собирает фильтры списка новостей из query-параметров запроса."""
    return NewsFilterSchema(name=name, weight_from=weight_from, weight_to=weight_to)
