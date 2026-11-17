from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.audios.constants import AUDIO_TYPES_HINT
from app.audios.filter import get_audio_filters
from app.audios.schema.audios import (
    AudioFilterSchema,
    AudioPlaybackSchema,
    AudioResponseSchema,
    AudioTypeSchema,
    AudioUpdateSchema,
)
from app.audios.service.audios import AudiosService
from app.auth.dependencies import bearer_scheme
from app.core.dependencies import PaginatorDep
from app.core.schemes import PaginatedSchema
from app.users.schema.users import UserResponseSchema

# Все операции с аудио доступны только авторизованным пользователям:
# загрузка, чтение, список и presigned-ссылки — любому зарегистрированному пользователю,
# переименование и удаление — администратору (любое аудио) или автору загрузки.
router = APIRouter(prefix='/audios', tags=['audios'])


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    summary='Загрузка аудио в S3-хранилище (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def upload_audio(
    audios_service: FromDishka[AudiosService],
    user: FromDishka[UserResponseSchema],
    name: Annotated[str, Form(min_length=1, max_length=255, description='Уникальное имя аудио')],
    file: Annotated[UploadFile, File(description=f'Аудио: {AUDIO_TYPES_HINT}')],
    folder_id: Annotated[
        UUID | None, Form(description='Папка пользователя, в которую сразу кладётся аудио')
    ] = None,
) -> AudioResponseSchema:
    return await audios_service.upload(
        name=name, filename=file.filename, stream=file.file, size=file.size, folder_id=folder_id
    )


@router.get(
    '',
    summary='Список аудио с фильтрами и пагинацией (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_audios(
    audios_service: FromDishka[AudiosService],
    user: FromDishka[UserResponseSchema],
    filters: Annotated[AudioFilterSchema, Depends(get_audio_filters)],
    paginator: PaginatorDep,
) -> PaginatedSchema[AudioResponseSchema]:
    return await audios_service.get_list(filters=filters, paginator=paginator)


@router.get(
    '/types',
    summary='Справочник разрешённых типов аудио (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_audio_types(
    audios_service: FromDishka[AudiosService], user: FromDishka[UserResponseSchema]
) -> list[AudioTypeSchema]:
    """Отдаёт фронтенду типы: для фильтра `?type=` и атрибута `accept` формы."""
    return audios_service.get_types()


@router.get(
    '/by-name',
    summary='Аудио по точному имени (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_audio_by_name(
    audios_service: FromDishka[AudiosService],
    user: FromDishka[UserResponseSchema],
    name: Annotated[str, Query(min_length=1, max_length=255, description='Точное имя аудио')],
) -> AudioResponseSchema:
    return await audios_service.get_one_by_name(name=name)


@router.get(
    '/{audio_id}',
    summary='Аудио по идентификатору (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_audio(
    audio_id: UUID, audios_service: FromDishka[AudiosService], user: FromDishka[UserResponseSchema]
) -> AudioResponseSchema:
    return await audios_service.get_one(pk=audio_id)


@router.get(
    '/{audio_id}/playback',
    summary='Presigned-ссылка на воспроизведение аудио (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_audio_playback(
    audio_id: UUID, audios_service: FromDishka[AudiosService], user: FromDishka[UserResponseSchema]
) -> AudioPlaybackSchema:
    return await audios_service.get_playback(pk=audio_id)


@router.patch(
    '/{audio_id}',
    summary='Переименование аудио (администратор — любое, пользователь — только своё)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def update_audio(
    audio_id: UUID,
    data: AudioUpdateSchema,
    audios_service: FromDishka[AudiosService],
    user: FromDishka[UserResponseSchema],
) -> AudioResponseSchema:
    return await audios_service.update(pk=audio_id, data=data, user=user)


@router.delete(
    '/{audio_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление аудио (администратор — любое, пользователь — только своё)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def delete_audio(
    audio_id: UUID, audios_service: FromDishka[AudiosService], user: FromDishka[UserResponseSchema]
) -> None:
    await audios_service.delete(pk=audio_id, user=user)
