from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.requests import Request

from app.audios.constants import AUDIO_TYPES
from app.audios.endpoint.audios import router as audios_router
from app.audios.service.audios import AudiosService
from app.core.di import build_dishka_container
from app.core.enums import EAudioType
from app.folders.service.folders import FoldersService
from tests.fakes import (
    FakeAudiosRepository,
    FakeFileStorage,
    FakeFoldersRepository,
    seed_audio,
    seed_folder,
)

AUDIO_BYTES = b'ID3\x03\x00\x00\x00\x00\x00\x00test-audio'


async def upload_audio(
    client: AsyncClient,
    *,
    name: str = 'Аудио',
    filename: str = 'audio.mp3',
    data: bytes = AUDIO_BYTES,
    folder_id=None,
):
    """Загружает аудио через REST так же, как это делает клиент."""
    form = {'name': name}
    if folder_id is not None:
        form['folder_id'] = str(folder_id)
    return await client.post(
        '/api/audios', data=form, files={'file': (filename, data, 'audio/mpeg')}
    )


@pytest.mark.parametrize('extension', sorted(AUDIO_TYPES))
async def test_upload_accepts_allowed_types(client: AsyncClient, extension: str):
    response = await upload_audio(client, filename=f'track.{extension}', data=b'audio-data')

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Аудио'
    assert body['type'] == extension
    assert body['size'] == len(b'audio-data')
    assert body['object_key'].startswith('audios/')
    assert body['object_key'].endswith(f'.{extension}')
    assert body['id'] and body['created_at']


async def test_upload_puts_object_in_storage(client: AsyncClient, fake_storage: FakeFileStorage):
    response = await upload_audio(client)

    assert response.status_code == 201
    assert fake_storage.objects[response.json()['object_key']] == AUDIO_BYTES


async def test_upload_rejects_unsupported_type(client: AsyncClient):
    response = await upload_audio(client, filename='track.midi')

    assert response.status_code == 400
    assert 'Недопустимый тип аудио' in response.json()['detail']


async def test_upload_rejects_empty_file(client: AsyncClient):
    response = await upload_audio(client, data=b'')

    assert response.status_code == 400
    assert response.json()['detail'] == 'Файл пустой.'


async def test_upload_rejects_too_large_file(client: AsyncClient):
    response = await upload_audio(client, data=b'0' * (1024 * 1024 + 1))

    assert response.status_code == 400
    assert 'Размер файла превышает 1 МБ' in response.json()['detail']


async def test_upload_rejects_duplicate_name(client: AsyncClient, fake_storage: FakeFileStorage):
    assert (await upload_audio(client, name='Джингл')).status_code == 201

    response = await upload_audio(client, name='Джингл')

    assert response.status_code == 409
    assert 'Джингл' in response.json()['detail']
    assert len(fake_storage.objects) == 1


async def test_upload_cleans_object_when_name_taken_in_race(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    fake_audios_repository.conflict_on_create = True

    response = await upload_audio(client, name='Гонка')

    assert response.status_code == 409
    assert fake_storage.objects == {}


async def test_upload_into_folder(client: AsyncClient):
    """`folder_id` сразу кладёт загруженное аудио в папку пользователя."""
    folder_id = (await client.post('/api/folders', json={'name': 'Подкасты'})).json()['id']

    response = await upload_audio(client, name='Выпуск 1', folder_id=folder_id)

    assert response.status_code == 201
    folder = (await client.get(f'/api/folders/{folder_id}')).json()
    assert [item['name'] for item in folder['audios']] == ['Выпуск 1']
    assert folder['audios'][0]['id'] == response.json()['id']


async def test_upload_into_foreign_folder_is_rejected(
    client_as_client: AsyncClient,
    fake_folders_repository: FakeFoldersRepository,
    fake_storage: FakeFileStorage,
):
    """В чужую папку аудио не положить: отказ до загрузки объекта в хранилище."""
    folder = await seed_folder(fake_folders_repository, name='Чужая', creator_id=uuid4())

    response = await upload_audio(client_as_client, name='Чужое', folder_id=folder.id)

    assert response.status_code == 400
    assert 'Папка не найдена' in response.json()['detail']
    assert fake_storage.objects == {}


async def test_list_supports_filters_and_pagination(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    await seed_audio(
        fake_audios_repository, fake_storage, name='Демо трек', audio_type=EAudioType.MP3
    )
    await seed_audio(
        fake_audios_repository, fake_storage, name='Пример речи', audio_type=EAudioType.WAV
    )
    await seed_audio(
        fake_audios_repository, fake_storage, name='Демо голос', audio_type=EAudioType.WAV
    )

    response = await client.get('/api/audios')

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 3
    assert body['page'] == 1
    assert body['page_size'] == 25

    by_type = await client.get('/api/audios', params={'type': 'wav'})
    assert sorted(item['name'] for item in by_type.json()['data']) == ['Демо голос', 'Пример речи']

    by_types = await client.get('/api/audios', params=[('type', 'mp3'), ('type', 'wav')])
    assert by_types.json()['count'] == 3

    by_name = await client.get('/api/audios', params={'name': 'демо'})
    assert sorted(item['name'] for item in by_name.json()['data']) == ['Демо голос', 'Демо трек']

    page = await client.get('/api/audios', params={'page': 2, 'page_size': 2})
    page_body = page.json()
    assert page_body['count'] == 3
    assert page_body['offset'] == 2
    assert len(page_body['data']) == 1


async def test_get_by_name_returns_exact_match(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(fake_audios_repository, fake_storage, name='Демо трек')

    response = await client.get('/api/audios/by-name', params={'name': 'Демо трек'})

    assert response.status_code == 200
    assert response.json()['id'] == str(audio.id)

    case_mismatch = await client.get('/api/audios/by-name', params={'name': 'демо трек'})
    assert case_mismatch.status_code == 404

    missing = await client.get('/api/audios/by-name', params={'name': 'Нет такого'})
    assert missing.status_code == 404


async def test_get_audio_by_id(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(fake_audios_repository, fake_storage, name='Запись')

    response = await client.get(f'/api/audios/{audio.id}')

    assert response.status_code == 200
    assert response.json()['id'] == str(audio.id)
    assert (await client.get(f'/api/audios/{uuid4()}')).status_code == 404


async def test_playback_returns_presigned_url(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(fake_audios_repository, fake_storage, name='Трек')

    response = await client.get(f'/api/audios/{audio.id}/playback')

    assert response.status_code == 200
    body = response.json()
    assert body['url'] == (
        f'https://storage.test/cloudmanager-files/{audio.object_key}?X-Amz-Expires=3600'
    )
    assert body['content_type'] == 'audio/mpeg'
    assert body['expires_in'] == 3600
    assert body['expires_at']


async def test_playback_unknown_audio_is_404(client: AsyncClient):
    response = await client.get(f'/api/audios/{uuid4()}/playback')

    assert response.status_code == 404


async def test_types_endpoint_lists_allowed_types(client_as_client: AsyncClient):
    response = await client_as_client.get('/api/audios/types')

    assert response.status_code == 200
    assert response.json() == [
        {'value': 'mp3', 'content_type': 'audio/mpeg'},
        {'value': 'wav', 'content_type': 'audio/wav'},
        {'value': 'ogg', 'content_type': 'audio/ogg'},
        {'value': 'aac', 'content_type': 'audio/aac'},
        {'value': 'flac', 'content_type': 'audio/flac'},
        {'value': 'm4a', 'content_type': 'audio/mp4'},
        {'value': 'opus', 'content_type': 'audio/opus'},
        {'value': 'webm', 'content_type': 'audio/webm'},
    ]


async def test_rename_own_audio(client_as_client: AsyncClient, fake_storage: FakeFileStorage):
    created = (await upload_audio(client_as_client, name='Черновик')).json()

    response = await client_as_client.patch(f'/api/audios/{created["id"]}', json={'name': 'Финал'})

    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'Финал'
    assert body['object_key'] == created['object_key']
    assert body['type'] == created['type']
    assert body['size'] == created['size']
    assert fake_storage.objects[created['object_key']] == AUDIO_BYTES


async def test_rename_audio_empty_patch_keeps_name(client_as_client: AsyncClient):
    created = (await upload_audio(client_as_client, name='Неизменный')).json()

    response = await client_as_client.patch(f'/api/audios/{created["id"]}', json={})

    assert response.status_code == 200
    assert response.json()['name'] == 'Неизменный'


async def test_rename_audio_to_same_name_succeeds(client_as_client: AsyncClient):
    created = (await upload_audio(client_as_client, name='То же имя')).json()

    response = await client_as_client.patch(
        f'/api/audios/{created["id"]}', json={'name': 'То же имя'}
    )

    assert response.status_code == 200
    assert response.json()['name'] == 'То же имя'


async def test_rename_audio_rejects_duplicate_name(
    client_as_client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    await seed_audio(fake_audios_repository, fake_storage, name='Занято')
    own = (await upload_audio(client_as_client, name='Своё')).json()

    response = await client_as_client.patch(f'/api/audios/{own["id"]}', json={'name': 'Занято'})

    assert response.status_code == 409
    assert 'Занято' in response.json()['detail']


async def test_rename_audio_handles_race_conflict(
    client_as_client: AsyncClient, fake_audios_repository: FakeAudiosRepository
):
    own = (await upload_audio(client_as_client, name='Своё')).json()
    fake_audios_repository.conflict_on_update = True

    response = await client_as_client.patch(f'/api/audios/{own["id"]}', json={'name': 'Новое'})

    assert response.status_code == 409


async def test_rename_foreign_audio_is_forbidden(
    client_as_client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(
        fake_audios_repository, fake_storage, name='Чужое', creator_id=uuid4()
    )

    response = await client_as_client.patch(
        f'/api/audios/{audio.id}', json={'name': 'Перехвачено'}
    )

    assert response.status_code == 403
    assert response.json()['detail'] == 'Можно переименовывать только свои аудио.'


async def test_admin_renames_foreign_audio(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(
        fake_audios_repository, fake_storage, name='Чужое', creator_id=uuid4()
    )

    response = await client.patch(f'/api/audios/{audio.id}', json={'name': 'Обновлено'})

    assert response.status_code == 200
    assert response.json()['name'] == 'Обновлено'


async def test_rename_unknown_audio_is_404(client: AsyncClient):
    response = await client.patch(f'/api/audios/{uuid4()}', json={'name': 'Новое'})

    assert response.status_code == 404


async def test_delete_removes_record_and_object(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(fake_audios_repository, fake_storage, name='Демо')
    assert audio.object_key in fake_storage.objects

    response = await client.delete(f'/api/audios/{audio.id}')

    assert response.status_code == 204
    assert audio.object_key not in fake_storage.objects
    assert (await client.get(f'/api/audios/{audio.id}')).status_code == 404
    # После удаления имя можно использовать повторно
    assert (await upload_audio(client, name='Демо')).status_code == 201


async def test_delete_own_audio(client_as_client: AsyncClient, fake_storage: FakeFileStorage):
    uploaded = await upload_audio(client_as_client, name='Своё')

    response = await client_as_client.delete(f'/api/audios/{uploaded.json()["id"]}')

    assert response.status_code == 204
    assert fake_storage.objects == {}


async def test_delete_foreign_audio_is_forbidden(
    client_as_client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(
        fake_audios_repository, fake_storage, name='Чужое', creator_id=uuid4()
    )

    response = await client_as_client.delete(f'/api/audios/{audio.id}')

    assert response.status_code == 403
    assert response.json()['detail'] == 'Можно удалять только свои аудио.'
    assert audio.object_key in fake_storage.objects


async def test_admin_deletes_foreign_audio(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    audio = await seed_audio(
        fake_audios_repository, fake_storage, name='Чужое', creator_id=uuid4()
    )

    response = await client.delete(f'/api/audios/{audio.id}')

    assert response.status_code == 204
    assert audio.object_key not in fake_storage.objects


async def test_all_audio_endpoints_require_auth(
    client_without_token: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_audios_repository: FakeAudiosRepository,
):
    """Весь модуль аудио доступен только авторизованным пользователям."""
    audio = await seed_audio(fake_audios_repository, fake_storage, name='Демо')

    assert (await upload_audio(client_without_token)).status_code == 401
    assert (await client_without_token.get('/api/audios')).status_code == 401
    assert (await client_without_token.get('/api/audios/types')).status_code == 401
    assert (
        await client_without_token.get('/api/audios/by-name', params={'name': 'Демо'})
    ).status_code == 401
    assert (await client_without_token.get(f'/api/audios/{audio.id}')).status_code == 401
    assert (await client_without_token.get(f'/api/audios/{audio.id}/playback')).status_code == 401
    assert (
        await client_without_token.patch(f'/api/audios/{audio.id}', json={'name': 'Новое'})
    ).status_code == 401
    assert (await client_without_token.delete(f'/api/audios/{audio.id}')).status_code == 401


def test_openapi_marks_all_audio_endpoints_as_protected():
    """Все ручки аудио требуют Bearer-токен в OpenAPI."""
    app = FastAPI()
    app.include_router(audios_router, prefix='/api')
    paths = app.openapi()['paths']

    assert all(
        'security' in method
        for method in (
            paths['/api/audios']['post'],
            paths['/api/audios']['get'],
            paths['/api/audios/types']['get'],
            paths['/api/audios/by-name']['get'],
            paths['/api/audios/{audio_id}']['get'],
            paths['/api/audios/{audio_id}/playback']['get'],
            paths['/api/audios/{audio_id}']['patch'],
            paths['/api/audios/{audio_id}']['delete'],
        )
    )


async def test_di_container_resolves_audios_and_folders_services():
    """Реальный Dishka-контейнер корректно собирает AudiosService и FoldersService."""
    container = build_dishka_container()
    request = Request({'type': 'http', 'headers': []})
    try:
        async with container(context={Request: request}) as scope:
            assert isinstance(await scope.get(AudiosService), AudiosService)
            assert isinstance(await scope.get(FoldersService), FoldersService)
    finally:
        await container.close()
