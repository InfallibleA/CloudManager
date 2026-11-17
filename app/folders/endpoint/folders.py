from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import bearer_scheme
from app.core.dependencies import PaginatorDep
from app.core.schemes import PaginatedSchema
from app.folders.filter import get_folder_filters
from app.folders.schema.folders import (
    FolderCreateSchema,
    FolderFilterSchema,
    FolderResponseSchema,
    FolderUpdateSchema,
)
from app.folders.service.folders import FoldersService
from app.users.schema.users import UserResponseSchema

# Папки — личное пространство: всё под авторизацией, и любой пользователь работает
# только со своими папками (владелец — creator_id, фильтр живёт в репозитории).
router = APIRouter(prefix='/folders', tags=['folders'])


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    summary='Создание папки (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def create_folder(
    folders_service: FromDishka[FoldersService],
    user: FromDishka[UserResponseSchema],
    data: FolderCreateSchema,
) -> FolderResponseSchema:
    """Создаёт папку: `parent_id` делает её вложенной, а *_ids сразу кладут содержимое."""
    return await folders_service.create(data=data)


@router.get(
    '',
    summary='Список папок (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_folders(
    folders_service: FromDishka[FoldersService],
    user: FromDishka[UserResponseSchema],
    filters: Annotated[FolderFilterSchema, Depends(get_folder_filters)],
    paginator: PaginatorDep,
) -> PaginatedSchema[FolderResponseSchema]:
    """Отдаёт папки пользователя: фильтры `name`, `parent_id`, `root_only`,
    `creator_id` (только для админа) и пагинация.
    """
    return await folders_service.get_list(filters=filters, paginator=paginator)


@router.get(
    '/{folder_id}',
    summary='Папка с файлами и подпапками (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_folder(
    folder_id: UUID,
    folders_service: FromDishka[FoldersService],
    user: FromDishka[UserResponseSchema],
) -> FolderResponseSchema:
    return await folders_service.get_one(pk=folder_id)


@router.patch(
    '/{folder_id}',
    summary='Изменение папки: имя, родитель, файлы (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def update_folder(
    folder_id: UUID,
    data: FolderUpdateSchema,
    folders_service: FromDishka[FoldersService],
    user: FromDishka[UserResponseSchema],
) -> FolderResponseSchema:
    """`*_ids` — полные новые наборы содержимого, `parent_id: null` переносит папку в корень."""
    return await folders_service.update(pk=folder_id, data=data)


@router.delete(
    '/{folder_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление папки со всеми подпапками и файлами внутри',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def delete_folder(
    folder_id: UUID,
    folders_service: FromDishka[FoldersService],
    user: FromDishka[UserResponseSchema],
) -> None:
    await folders_service.delete(pk=folder_id)
