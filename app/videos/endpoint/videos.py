from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth.dependencies import bearer_scheme
from app.core.dependencies import PaginatorDep
from app.core.schemes import PaginatedSchema
from app.users.schema.users import UserResponseSchema
from app.videos.constants import VIDEO_TYPES_HINT
from app.videos.filter import get_video_filters
from app.videos.schema.videos import (
    VideoFilterSchema,
    VideoPlaybackSchema,
    VideoResponseSchema,
    VideoTypeSchema,
)
from app.videos.service.videos import VideosService

# Чтение и воспроизведение открыты всем: видео играет страница сайта, ссылку на
# файл защищает подпись. Загрузка доступна любому авторизованному пользователю,
# удаление — администратору (любое видео) или автору загрузки.
router = APIRouter(prefix='/videos', tags=['videos'])


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    summary='Загрузка видео в S3-хранилище (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def upload_video(
    videos_service: FromDishka[VideosService],
    user: FromDishka[UserResponseSchema],
    name: Annotated[str, Form(min_length=1, max_length=255, description='Уникальное имя видео')],
    file: Annotated[UploadFile, File(description=f'Видео: {VIDEO_TYPES_HINT}')],
) -> VideoResponseSchema:
    return await videos_service.upload(
        name=name, filename=file.filename, stream=file.file, size=file.size
    )


@router.get('', summary='Список видео с фильтрами и пагинацией (без авторизации)')
@inject
async def get_videos(
    videos_service: FromDishka[VideosService],
    filters: Annotated[VideoFilterSchema, Depends(get_video_filters)],
    paginator: PaginatorDep,
) -> PaginatedSchema[VideoResponseSchema]:
    return await videos_service.get_list(filters=filters, paginator=paginator)


@router.get('/types', summary='Справочник разрешённых типов видео (без авторизации)')
@inject
async def get_video_types(videos_service: FromDishka[VideosService]) -> list[VideoTypeSchema]:
    """Отдаёт фронтенду типы: для фильтра `?type=` и атрибута `accept` формы."""
    return videos_service.get_types()


@router.get('/by-name', summary='Видео по точному имени (без авторизации)')
@inject
async def get_video_by_name(
    videos_service: FromDishka[VideosService],
    name: Annotated[str, Query(min_length=1, max_length=255, description='Точное имя видео')],
) -> VideoResponseSchema:
    return await videos_service.get_one_by_name(name=name)


@router.get('/{video_id}', summary='Видео по идентификатору (без авторизации)')
@inject
async def get_video(
    video_id: UUID, videos_service: FromDishka[VideosService]
) -> VideoResponseSchema:
    return await videos_service.get_one(pk=video_id)


@router.get(
    '/{video_id}/playback', summary='Presigned-ссылка на воспроизведение видео (без авторизации)'
)
@inject
async def get_video_playback(
    video_id: UUID, videos_service: FromDishka[VideosService]
) -> VideoPlaybackSchema:
    return await videos_service.get_playback(pk=video_id)


@router.delete(
    '/{video_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление видео (администратор — любое, пользователь — только своё)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def delete_video(
    video_id: UUID, videos_service: FromDishka[VideosService], user: FromDishka[UserResponseSchema]
) -> None:
    await videos_service.delete(pk=video_id, user=user)
