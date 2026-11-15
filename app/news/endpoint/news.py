from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import bearer_scheme
from app.core.dependencies import PaginatorDep
from app.core.schemes import PaginatedSchema
from app.news.filter import get_news_filters
from app.news.schema.news import (
    NewsCreateSchema,
    NewsFilterSchema,
    NewsResponseSchema,
    NewsUpdateSchema,
)
from app.news.service.news import NewsService
from app.users.schema.users import AdminUserSchema

# Чтение новостей доступно без авторизации, поэтому bearer-схема — только у мутаций.
router = APIRouter(prefix='/news', tags=['news'])


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    summary='Создание новости (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def create_news(
    news_service: FromDishka[NewsService],
    admin: FromDishka[AdminUserSchema],
    data: NewsCreateSchema,
) -> NewsResponseSchema:
    return await news_service.create(data=data)


@router.get(
    '', summary='Список новостей без авторизации: фильтры по имени и весу, сортировка по весу'
)
@inject
async def get_news_list(
    news_service: FromDishka[NewsService],
    filters: Annotated[NewsFilterSchema, Depends(get_news_filters)],
    paginator: PaginatorDep,
) -> PaginatedSchema[NewsResponseSchema]:
    return await news_service.get_list(filters=filters, paginator=paginator)


@router.get('/{news_id}', summary='Новость по идентификатору без авторизации')
@inject
async def get_news(
    news_id: UUID,
    news_service: FromDishka[NewsService],
) -> NewsResponseSchema:
    return await news_service.get_one(pk=news_id)


@router.patch(
    '/{news_id}',
    summary='Обновление новости: имя, описание, вес, файлы, медиа (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def update_news(
    news_id: UUID,
    data: NewsUpdateSchema,
    news_service: FromDishka[NewsService],
    admin: FromDishka[AdminUserSchema],
) -> NewsResponseSchema:
    return await news_service.update(pk=news_id, data=data)


@router.delete(
    '/{news_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление новости (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def delete_news(
    news_id: UUID,
    news_service: FromDishka[NewsService],
    admin: FromDishka[AdminUserSchema],
) -> None:
    await news_service.delete(pk=news_id)
