from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.requests import Request

from app.auth.dependencies import extract_bearer_token
from app.core.enums import EFileType, EUserRole
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.files.constants import FILE_TYPES, IMAGE_TYPES
from app.routers import router
from app.users.schema.users import AdminUserSchema, UserResponseSchema
from tests.conftest import ADMIN_USER_ID, CLIENT_USER_ID
from tests.fakes import (
    FakeFilesRepository,
    FakeFileStorage,
    seed_file,
)

PDF_BYTES = b'%PDF-1.4 test document'
PNG_BYTES = b'\x89PNG\r\n\x1a\n image'

# Ожидаемый MIME для каждого разрешённого расширения-картинки
IMAGE_CONTENT_TYPES = {
    'gif': 'image/gif',
    'jpeg': 'image/jpeg',
    'jpg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
    'avif': 'image/avif',
}


async def upload_file(
    client: AsyncClient,
    *,
    name: str = 'Документ',
    filename: str = 'document.pdf',
    data: bytes = PDF_BYTES,
):
    """Загружает файл через REST так же, как это делает фронтенд."""
    return await client.post(
        '/api/files',
        data={'name': name},
        files={'file': (filename, data, 'application/octet-stream')},
    )


@pytest.mark.parametrize('extension', sorted(FILE_TYPES))
async def test_upload_accepts_allowed_types(client: AsyncClient, extension: str):
    response = await upload_file(client, filename=f'document.{extension}', data=b'file-data')

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Документ'
    assert body['type'] == extension
    assert body['size'] == len(b'file-data')
    assert body['object_key'].endswith(f'.{extension}')
    assert body['id'] and body['created_at']


async def test_upload_puts_object_in_storage(client: AsyncClient, fake_storage: FakeFileStorage):
    response = await upload_file(client)

    assert response.status_code == 201
    assert fake_storage.objects[response.json()['object_key']] == PDF_BYTES


async def test_upload_rejects_unsupported_type(client: AsyncClient):
    response = await upload_file(client, filename='virus.exe')

    assert response.status_code == 400
    assert 'Недопустимый тип файла' in response.json()['detail']


async def test_upload_rejects_empty_file(client: AsyncClient):
    response = await upload_file(client, data=b'')

    assert response.status_code == 400
    assert response.json()['detail'] == 'Файл пустой.'


async def test_upload_rejects_too_large_file(client: AsyncClient):
    response = await upload_file(client, data=b'0' * (1024 * 1024 + 1))

    assert response.status_code == 400
    assert 'Размер файла превышает 1 МБ' in response.json()['detail']


async def test_list_supports_filters_and_pagination(client: AsyncClient):
    await upload_file(client, name='Договор', filename='dogovor.pdf')
    await upload_file(client, name='Смета', filename='smeta.xlsx', data=b'xlsx-data')
    await upload_file(client, name='Схема', filename='schema.png', data=PNG_BYTES)

    response = await client.get('/api/files')

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 3
    assert body['page'] == 1
    assert body['page_size'] == 25
    assert len(body['data']) == 3
    # владелец готов к показу в колонке «Пользователь»
    assert all(item['creator_id'] == str(ADMIN_USER_ID) for item in body['data'])
    assert all(item['creator_login'] == 'admin' for item in body['data'])

    by_type = await client.get('/api/files', params={'type': 'xlsx'})
    assert [item['name'] for item in by_type.json()['data']] == ['Смета']

    by_types = await client.get('/api/files', params=[('type', 'xlsx'), ('type', 'png')])
    assert sorted(item['name'] for item in by_types.json()['data']) == ['Смета', 'Схема']

    by_name = await client.get('/api/files', params={'name': 'догов'})
    assert [item['name'] for item in by_name.json()['data']] == ['Договор']

    page = await client.get('/api/files', params={'page': 2, 'page_size': 2})

    page_body = page.json()
    assert page_body['count'] == 3
    assert page_body['offset'] == 2
    assert len(page_body['data']) == 1


async def test_list_filters_by_creator(
    client: AsyncClient, client_as_client: AsyncClient
):
    """Список файлов фильтруется по пользователю-владельцу."""
    await upload_file(client, name='Админский')
    await upload_file(client_as_client, name='Клиентский')

    response = await client.get('/api/files', params={'creator_id': str(CLIENT_USER_ID)})

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 1
    assert [item['name'] for item in body['data']] == ['Клиентский']
    assert body['data'][0]['creator_id'] == str(CLIENT_USER_ID)
    assert body['data'][0]['creator_login'] == 'client'


async def test_download_returns_file_content(client: AsyncClient):
    uploaded = (await upload_file(client, filename='schema.png', data=PNG_BYTES)).json()

    response = await client.get(f'/api/files/{uploaded["id"]}/download')

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers['content-type'] == 'image/png'
    assert 'attachment' in response.headers['content-disposition']


async def test_download_unknown_file_returns_404(client: AsyncClient):
    response = await client.get(f'/api/files/{uuid4()}/download')

    assert response.status_code == 404


async def test_image_returns_inline_content(client: AsyncClient):
    uploaded = (await upload_file(client, filename='schema.png', data=PNG_BYTES)).json()

    response = await client.get(f'/api/files/{uploaded["id"]}/image')

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers['content-type'] == 'image/png'
    assert response.headers['content-disposition'].startswith('inline')
    assert response.headers['cache-control'] == 'public, max-age=86400, immutable'
    assert response.headers['etag']


async def test_image_rejects_non_image(client: AsyncClient):
    uploaded = (await upload_file(client)).json()

    response = await client.get(f'/api/files/{uploaded["id"]}/image')

    assert response.status_code == 400
    assert response.json()['detail'] == (
        'Файл не является изображением. Разрешены: avif, gif, jpeg, jpg, png, webp.'
    )


@pytest.mark.parametrize(('extension', 'content_type'), sorted(IMAGE_CONTENT_TYPES.items()))
async def test_image_serves_every_image_type(
    client: AsyncClient, extension: str, content_type: str
):
    uploaded = (
        await upload_file(client, filename=f'photo.{extension}', data=b'image-data')
    ).json()

    response = await client.get(f'/api/files/{uploaded["id"]}/image')

    assert response.status_code == 200
    assert response.content == b'image-data'
    assert response.headers['content-type'] == content_type
    assert response.headers['x-content-type-options'] == 'nosniff'


async def test_image_response_has_no_csp(client: AsyncClient):
    uploaded = (await upload_file(client, filename='photo.webp', data=b'image-data')).json()

    response = await client.get(f'/api/files/{uploaded["id"]}/image')

    assert response.status_code == 200
    assert 'content-security-policy' not in response.headers


async def test_image_unknown_file_returns_404(client: AsyncClient):
    response = await client.get(f'/api/files/{uuid4()}/image')

    assert response.status_code == 404


async def test_image_supports_etag_revalidation(client: AsyncClient):
    uploaded = (await upload_file(client, filename='schema.png', data=PNG_BYTES)).json()
    etag = (await client.get(f'/api/files/{uploaded["id"]}/image')).headers['etag']

    response = await client.get(
        f'/api/files/{uploaded["id"]}/image', headers={'If-None-Match': etag}
    )

    assert response.status_code == 304
    assert not response.content


async def test_image_is_public(
    client_without_token: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    file = await seed_file(
        fake_repository, fake_storage, name='Схема', file_type=EFileType.PNG, data=PNG_BYTES
    )

    response = await client_without_token.get(f'/api/files/{file.id}/image')

    assert response.status_code == 200
    assert response.content == PNG_BYTES


async def test_delete_removes_record_and_object(
    client: AsyncClient, fake_storage: FakeFileStorage
):
    uploaded = (await upload_file(client)).json()

    response = await client.delete(f'/api/files/{uploaded["id"]}')

    assert response.status_code == 204
    assert uploaded['object_key'] not in fake_storage.objects
    assert (await client.get('/api/files')).json()['count'] == 0
    assert (await client.get(f'/api/files/{uploaded["id"]}/download')).status_code == 404


async def test_delete_unknown_file_returns_404(client: AsyncClient):
    response = await client.delete(f'/api/files/{uuid4()}')

    assert response.status_code == 404


async def test_admin_renames_file(client: AsyncClient, fake_storage: FakeFileStorage):
    """Переименование меняет только имя в БД: сам объект и его метаданные не трогаются."""
    uploaded = (await upload_file(client)).json()

    response = await client.patch(f'/api/files/{uploaded["id"]}', json={'name': 'Договор'})

    assert response.status_code == 200
    renamed = response.json()
    assert renamed['name'] == 'Договор'
    assert renamed['object_key'] == uploaded['object_key']
    assert renamed['type'] == uploaded['type']
    assert renamed['size'] == uploaded['size']
    assert fake_storage.objects[uploaded['object_key']] == PDF_BYTES


async def test_empty_rename_keeps_file_as_is(client: AsyncClient):
    """Пустой патч — не ошибка: возвращается текущая запись."""
    uploaded = (await upload_file(client)).json()

    response = await client.patch(f'/api/files/{uploaded["id"]}', json={})

    assert response.status_code == 200
    assert response.json()['name'] == uploaded['name']


async def test_rename_with_empty_name_returns_422(client: AsyncClient):
    uploaded = (await upload_file(client)).json()

    response = await client.patch(f'/api/files/{uploaded["id"]}', json={'name': ''})

    assert response.status_code == 422


async def test_rename_unknown_file_returns_404(client: AsyncClient):
    response = await client.patch(f'/api/files/{uuid4()}', json={'name': 'Договор'})

    assert response.status_code == 404


async def test_client_renames_own_file(client_as_client: AsyncClient):
    uploaded = (await upload_file(client_as_client)).json()

    response = await client_as_client.patch(
        f'/api/files/{uploaded["id"]}', json={'name': 'Мой документ'}
    )

    assert response.status_code == 200
    assert response.json()['name'] == 'Мой документ'


async def test_client_cannot_rename_foreign_file(
    client_as_client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    file = await seed_file(
        fake_repository, fake_storage, name='Чужой', creator_id=ADMIN_USER_ID
    )

    response = await client_as_client.patch(f'/api/files/{file.id}', json={'name': 'Мой'})

    assert response.status_code == 403
    assert response.json()['error'] == 'ForbiddenException'
    assert fake_repository.items[file.id].name == 'Чужой'


def build_request(headers: dict[str, str]) -> Request:
    return Request(
        {
            'type': 'http',
            'headers': [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        }
    )


def test_extract_bearer_token_requires_header():
    with pytest.raises(UnauthorizedException):
        extract_bearer_token(build_request({}))


def test_extract_bearer_token_returns_token():
    token = extract_bearer_token(build_request({'Authorization': 'Bearer secret-token'}))

    assert token == 'secret-token'


async def test_upload_allowed_for_client(
    client_as_client: AsyncClient, fake_storage: FakeFileStorage
):
    """Загружать файлы может любой зарегистрированный пользователь, не только админ."""
    response = await upload_file(client_as_client)

    assert response.status_code == 201
    assert fake_storage.objects[response.json()['object_key']] == PDF_BYTES


async def test_client_deletes_own_file(
    client_as_client: AsyncClient, fake_storage: FakeFileStorage
):
    """Пользователь без роли админа может удалить свой файл."""
    uploaded = (await upload_file(client_as_client)).json()

    response = await client_as_client.delete(f'/api/files/{uploaded["id"]}')

    assert response.status_code == 204
    assert uploaded['object_key'] not in fake_storage.objects


async def test_client_cannot_delete_foreign_file(
    client_as_client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Чужой файл остаётся на месте: 403 и никаких изменений в хранилище."""
    file = await seed_file(fake_repository, fake_storage, creator_id=ADMIN_USER_ID)

    response = await client_as_client.delete(f'/api/files/{file.id}')

    assert response.status_code == 403
    assert response.json()['error'] == 'ForbiddenException'
    assert file.object_key in fake_storage.objects
    assert (await client_as_client.get(f'/api/files/{file.id}/download')).status_code == 200


async def test_admin_deletes_foreign_file(
    client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Админ удаляет любой файл, в том числе загруженный другим пользователем."""
    file = await seed_file(fake_repository, fake_storage, creator_id=CLIENT_USER_ID)

    response = await client.delete(f'/api/files/{file.id}')

    assert response.status_code == 204
    assert file.object_key not in fake_storage.objects
    assert (await client.get('/api/files')).json()['count'] == 0


async def test_client_can_list_and_download(
    client_as_client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    file = await seed_file(fake_repository, fake_storage, file_type=EFileType.PNG, data=PNG_BYTES)

    listing = await client_as_client.get('/api/files')
    download = await client_as_client.get(f'/api/files/{file.id}/download')

    assert listing.status_code == 200
    assert listing.json()['count'] == 1
    assert download.status_code == 200
    assert download.content == PNG_BYTES


async def test_download_without_token(
    client_without_token: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Скачивание по id доступно без авторизации — ради ссылок из витрины."""
    file = await seed_file(fake_repository, fake_storage, file_type=EFileType.PNG, data=PNG_BYTES)

    response = await client_without_token.get(f'/api/files/{file.id}/download')

    assert response.status_code == 200
    assert response.content == PNG_BYTES


async def test_other_file_endpoints_need_token(
    client_without_token: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    file = await seed_file(fake_repository, fake_storage)

    upload = await upload_file(client_without_token)
    listing = await client_without_token.get('/api/files')
    delete = await client_without_token.delete(f'/api/files/{file.id}')
    rename = await client_without_token.patch(
        f'/api/files/{file.id}', json={'name': 'Договор'}
    )

    assert upload.status_code == 401
    assert listing.status_code == 401
    assert delete.status_code == 401
    assert rename.status_code == 401


def test_openapi_marks_download_as_public():
    """Скачивание и показ картинки — без bearer-схемы, остальные ручки файлов — под ней."""
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()['paths']

    assert 'security' not in paths['/api/files/types']['get']
    assert 'security' not in paths['/api/files/{file_id}/download']['get']
    assert 'security' not in paths['/api/files/{file_id}/image']['get']
    assert all(
        'security' in method
        for method in (
            paths['/api/files']['get'],
            paths['/api/files']['post'],
            paths['/api/files/{file_id}']['delete'],
            paths['/api/files/{file_id}']['patch'],
        )
    )


async def test_file_types_reference_is_public(client_without_token: AsyncClient):
    """Справочник типов доступен без токена: фронт берёт из него список для фильтра."""
    response = await client_without_token.get('/api/files/types')

    assert response.status_code == 200
    types = response.json()
    assert [item['value'] for item in types] == [file_type.value for file_type in EFileType]

    by_value = {item['value']: item for item in types}
    assert by_value['png'] == {'value': 'png', 'content_type': 'image/png', 'is_image': True}
    assert by_value['pdf']['content_type'] == 'application/pdf'
    assert by_value['pdf']['is_image'] is False
    assert by_value['txt'] == {'value': 'txt', 'content_type': 'text/plain', 'is_image': False}

    image_values = {item['value'] for item in types if item['is_image']}
    assert image_values == {image_type.value for image_type in IMAGE_TYPES}


def test_admin_user_schema_rejects_client(client_user: UserResponseSchema):
    with pytest.raises(ForbiddenException):
        AdminUserSchema.from_user(client_user)


def test_admin_user_schema_accepts_admin(admin_user: UserResponseSchema):
    assert AdminUserSchema.from_user(admin_user).role is EUserRole.ADMIN
