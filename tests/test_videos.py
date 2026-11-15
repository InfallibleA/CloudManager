from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.enums import EVideoType
from app.videos.constants import VIDEO_TYPES
from tests.fakes import FakeFileStorage, FakeVideosRepository, seed_video

VIDEO_BYTES = b'\x00\x00\x00\x18ftypmp42 test-video'


async def upload_video(
    client: AsyncClient,
    *,
    name: str = 'Видео',
    filename: str = 'video.mp4',
    data: bytes = VIDEO_BYTES,
):
    """Загружает видео через REST так же, как это делает фронтенд."""
    return await client.post(
        '/api/videos', data={'name': name}, files={'file': (filename, data, 'video/mp4')}
    )


@pytest.mark.parametrize('extension', sorted(VIDEO_TYPES))
async def test_upload_accepts_allowed_types(client: AsyncClient, extension: str):
    response = await upload_video(client, filename=f'video.{extension}', data=b'video-data')

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Видео'
    assert body['type'] == extension
    assert body['size'] == len(b'video-data')
    assert body['object_key'].startswith('videos/')
    assert body['object_key'].endswith(f'.{extension}')
    assert body['id'] and body['created_at']


async def test_upload_puts_object_in_storage(client: AsyncClient, fake_storage: FakeFileStorage):
    response = await upload_video(client)

    assert response.status_code == 201
    assert fake_storage.objects[response.json()['object_key']] == VIDEO_BYTES


async def test_upload_rejects_unsupported_type(client: AsyncClient):
    response = await upload_video(client, filename='video.avi')

    assert response.status_code == 400
    assert 'Недопустимый тип видео' in response.json()['detail']


async def test_upload_rejects_empty_file(client: AsyncClient):
    response = await upload_video(client, data=b'')

    assert response.status_code == 400
    assert response.json()['detail'] == 'Файл пустой.'


async def test_upload_rejects_too_large_file(client: AsyncClient):
    response = await upload_video(client, data=b'0' * (1024 * 1024 + 1))

    assert response.status_code == 400
    assert 'Размер файла превышает 1 МБ' in response.json()['detail']


async def test_upload_rejects_duplicate_name(client: AsyncClient, fake_storage: FakeFileStorage):
    assert (await upload_video(client, name='Демо')).status_code == 201

    response = await upload_video(client, name='Демо')

    assert response.status_code == 409
    assert 'Демо' in response.json()['detail']
    # Дубль отсечён до загрузки: в хранилище остался только первый объект
    assert len(fake_storage.objects) == 1


async def test_upload_cleans_object_when_name_taken_in_race(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    # Имя свободно при проверке, но занято при вставке — гонка двух загрузок
    fake_videos_repository.conflict_on_create = True

    response = await upload_video(client, name='Гонка')

    assert response.status_code == 409
    # Загруженный объект удалён: «сироты» в хранилище не остаётся
    assert fake_storage.objects == {}


async def test_list_supports_filters_and_pagination(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    await seed_video(
        fake_videos_repository, fake_storage, name='Демо склада', video_type=EVideoType.MP4
    )
    await seed_video(
        fake_videos_repository, fake_storage, name='Пример улицы', video_type=EVideoType.WEBM
    )
    await seed_video(
        fake_videos_repository, fake_storage, name='Демо парковки', video_type=EVideoType.WEBM
    )

    response = await client.get('/api/videos')

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 3
    assert body['page'] == 1
    assert body['page_size'] == 25

    by_type = await client.get('/api/videos', params={'type': 'webm'})
    assert sorted(item['name'] for item in by_type.json()['data']) == [
        'Демо парковки',
        'Пример улицы',
    ]

    by_types = await client.get('/api/videos', params=[('type', 'mp4'), ('type', 'webm')])
    assert by_types.json()['count'] == 3

    by_name = await client.get('/api/videos', params={'name': 'демо'})
    assert sorted(item['name'] for item in by_name.json()['data']) == [
        'Демо парковки',
        'Демо склада',
    ]

    page = await client.get('/api/videos', params={'page': 2, 'page_size': 2})
    page_body = page.json()
    assert page_body['count'] == 3
    assert page_body['offset'] == 2
    assert len(page_body['data']) == 1


async def test_get_by_name_returns_exact_match(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    video = await seed_video(fake_videos_repository, fake_storage, name='Демо склада')

    response = await client.get('/api/videos/by-name', params={'name': 'Демо склада'})

    assert response.status_code == 200
    assert response.json()['id'] == str(video.id)

    case_mismatch = await client.get('/api/videos/by-name', params={'name': 'демо склада'})
    assert case_mismatch.status_code == 404

    missing = await client.get('/api/videos/by-name', params={'name': 'Нет такого'})
    assert missing.status_code == 404


async def test_playback_returns_presigned_url(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    video = await seed_video(fake_videos_repository, fake_storage, name='Демо')

    response = await client.get(f'/api/videos/{video.id}/playback')

    assert response.status_code == 200
    body = response.json()
    assert body['url'] == (
        f'https://storage.test/cloudmanager-files/{video.object_key}?X-Amz-Expires=3600'
    )
    assert body['content_type'] == 'video/mp4'
    assert body['expires_in'] == 3600
    assert body['expires_at']


async def test_playback_unknown_video_is_404(client: AsyncClient):
    response = await client.get(f'/api/videos/{uuid4()}/playback')

    assert response.status_code == 404


async def test_delete_removes_record_and_object(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    video = await seed_video(fake_videos_repository, fake_storage, name='Демо')
    assert video.object_key in fake_storage.objects

    response = await client.delete(f'/api/videos/{video.id}')

    assert response.status_code == 204
    assert video.object_key not in fake_storage.objects
    assert (await client.get(f'/api/videos/{video.id}')).status_code == 404


async def test_types_endpoint_lists_allowed_types(client_without_token: AsyncClient):
    response = await client_without_token.get('/api/videos/types')

    assert response.status_code == 200
    assert response.json() == [
        {'value': 'mp4', 'content_type': 'video/mp4'},
        {'value': 'webm', 'content_type': 'video/webm'},
    ]


async def test_upload_available_to_any_authenticated_user(
    client_as_client: AsyncClient, client_without_token: AsyncClient
):
    assert (await upload_video(client_as_client)).status_code == 201
    assert (await upload_video(client_without_token)).status_code == 401


async def test_delete_own_video(
    client_as_client: AsyncClient,
    fake_storage: FakeFileStorage,
):
    uploaded = await upload_video(client_as_client, name='Своё')

    response = await client_as_client.delete(f'/api/videos/{uploaded.json()["id"]}')

    assert response.status_code == 204
    assert fake_storage.objects == {}


async def test_delete_foreign_video_is_forbidden(
    client_as_client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    video = await seed_video(
        fake_videos_repository, fake_storage, name='Чужое', creator_id=uuid4()
    )

    response = await client_as_client.delete(f'/api/videos/{video.id}')

    assert response.status_code == 403
    assert response.json()['detail'] == 'Можно удалять только свои видео.'
    assert video.object_key in fake_storage.objects


async def test_admin_deletes_foreign_video(
    client: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    video = await seed_video(
        fake_videos_repository, fake_storage, name='Чужое', creator_id=uuid4()
    )

    response = await client.delete(f'/api/videos/{video.id}')

    assert response.status_code == 204
    assert video.object_key not in fake_storage.objects


async def test_delete_requires_auth(client_without_token: AsyncClient):
    response = await client_without_token.delete(f'/api/videos/{uuid4()}')

    assert response.status_code == 401


async def test_read_endpoints_are_public(
    client_without_token: AsyncClient,
    fake_storage: FakeFileStorage,
    fake_videos_repository: FakeVideosRepository,
):
    video = await seed_video(fake_videos_repository, fake_storage, name='Демо')

    assert (await client_without_token.get('/api/videos')).status_code == 200
    assert (await client_without_token.get('/api/videos/types')).status_code == 200
    assert (
        await client_without_token.get('/api/videos/by-name', params={'name': 'Демо'})
    ).status_code == 200
    assert (await client_without_token.get(f'/api/videos/{video.id}')).status_code == 200
    assert (await client_without_token.get(f'/api/videos/{video.id}/playback')).status_code == 200
