from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status

from app.auth.dependencies import bearer_scheme
from app.core.dependencies import PaginatorDep
from app.core.schemes import PaginatedSchema
from app.files.constants import FILE_TYPES_HINT, content_type_for
from app.files.filter import get_file_filters
from app.files.schema.files import (
    FileFilterSchema,
    FileResponseSchema,
    FileTypeSchema,
    FileUpdateSchema,
)
from app.files.service.files import FilesService
from app.users.schema.users import UserResponseSchema

# Скачивание файла открыто всем: файл доступен по ссылке со своим id — иначе
# посетитель сайта не сможет открыть вложение новости. Остальные ручки — под авторизацией:
# загрузка и список доступны любому зарегистрированному пользователю; переименование и
# удаление — админу (любой файл) или владельцу файла.
router = APIRouter(prefix='/files', tags=['files'])


def _disposition(*, disposition: str, filename: str) -> str:
    """Собирает Content-Disposition с корректным именем файла в UTF-8."""
    return f"{disposition}; filename*=UTF-8''{quote(filename)}"


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    summary='Загрузка файла в S3-хранилище (только зарегистрированный пользователь)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def upload_file(
    files_service: FromDishka[FilesService],
    user: FromDishka[UserResponseSchema],
    name: Annotated[str, Form(min_length=1, max_length=255, description='Имя файла')],
    file: Annotated[
        UploadFile,
        File(description=f'Файл: {FILE_TYPES_HINT}'),
    ],
) -> FileResponseSchema:
    return await files_service.upload(name=name, filename=file.filename, data=await file.read())


@router.get(
    '',
    summary='Список файлов с фильтрами и пагинацией (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_files(
    files_service: FromDishka[FilesService],
    user: FromDishka[UserResponseSchema],
    filters: Annotated[FileFilterSchema, Depends(get_file_filters)],
    paginator: PaginatorDep,
) -> PaginatedSchema[FileResponseSchema]:
    return await files_service.get_list(filters=filters, paginator=paginator)


@router.get('/types', summary='Справочник разрешённых типов файлов (без авторизации)')
@inject
async def get_file_types(files_service: FromDishka[FilesService]) -> list[FileTypeSchema]:
    """Отдаёт фронтенду список типов: для фильтра `?type=`, `accept` и показа картинок."""
    return files_service.get_types()


@router.get('/{file_id}/download', summary='Скачивание файла по id (без авторизации)')
@inject
async def download_file(
    file_id: UUID,
    files_service: FromDishka[FilesService],
) -> Response:
    file, data = await files_service.download(pk=file_id)
    filename = f'{file.name}.{file.type.value}'
    return Response(
        content=data,
        media_type=content_type_for(file.type),
        headers={'Content-Disposition': _disposition(disposition='attachment', filename=filename)},
    )


@router.get(
    '/{file_id}/image',
    summary='Изображение по id для показа в <img> (без авторизации)',
)
@inject
async def get_file_image(
    file_id: UUID,
    request: Request,
    files_service: FromDishka[FilesService],
) -> Response:
    """Отдаёт картинку инлайном, чтобы фронт вставил её в `<img src>` без скачивания."""
    file, data = await files_service.get_image(pk=file_id)

    # Содержимое файла неизменно, а id уникален: кэш можно держать сутки без ревалидации.
    etag = f'"{file.object_key}"'
    if request.headers.get('If-None-Match') == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={'ETag': etag})

    filename = f'{file.name}.{file.type.value}'
    headers = {
        'Content-Disposition': _disposition(disposition='inline', filename=filename),
        'Cache-Control': 'public, max-age=86400, immutable',
        'ETag': etag,
        # Запрещаем браузеру «угадывать» тип: файл отдаётся только с нашим MIME
        'X-Content-Type-Options': 'nosniff',
    }

    return Response(content=data, media_type=content_type_for(file.type), headers=headers)


@router.patch(
    '/{file_id}',
    summary='Переименование файла (админ — любой, пользователь — только свой)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def update_file(
    file_id: UUID,
    data: FileUpdateSchema,
    files_service: FromDishka[FilesService],
    user: FromDishka[UserResponseSchema],
) -> FileResponseSchema:
    return await files_service.update(pk=file_id, data=data, user=user)


@router.delete(
    '/{file_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление файла (админ — любой, пользователь — только свой)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def delete_file(
    file_id: UUID,
    files_service: FromDishka[FilesService],
    user: FromDishka[UserResponseSchema],
) -> None:
    await files_service.delete(pk=file_id, user=user)
