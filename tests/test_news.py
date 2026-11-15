from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.enums import EFileType
from app.core.exceptions import ObjectNotFoundException
from app.news.schema.news import NewsCreateSchema
from app.routers import router
from tests.fakes import (
    FakeFilesRepository,
    FakeFileStorage,
    FakeNewsRepository,
    seed_file,
)


async def create_news(
    client: AsyncClient,
    *,
    name: str = 'Новость',
    description: str = 'Описание',
    media_id: str | None = None,
):
    """Создаёт новость через REST так же, как это делает фронтенд."""
    payload = {'name': name, 'description': description}
    if media_id is not None:
        payload['media_id'] = media_id
    return await client.post('/api/news', json=payload)


async def test_create_news(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    response = await create_news(client, name='Витрина')

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Витрина'
    assert body['description'] == 'Описание'
    assert body['weight'] == 0
    assert body['media_id'] is None
    assert body['id']


async def test_create_sets_next_weight(client: AsyncClient):
    first = await create_news(client, name='Первый')
    second = await create_news(client, name='Второй')

    assert first.json()['weight'] == 0
    assert second.json()['weight'] == 1


async def test_create_ignores_weight_from_client(client: AsyncClient):
    response = await client.post(
        '/api/news', json={'name': 'Товар', 'description': 'Описание', 'weight': 7}
    )

    assert response.status_code == 201
    assert response.json()['weight'] == 0


async def test_create_requires_name(client: AsyncClient):
    response = await client.post('/api/news', json={'name': ''})

    assert response.status_code == 422


async def test_create_with_image_media(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    """media_id принимается, если это файл-изображение, и отдаётся в ответе."""
    image = await seed_file(fake_repository, fake_storage, name='Обложка', file_type=EFileType.PNG)

    response = await create_news(client, name='Витрина', media_id=str(image.id))

    assert response.status_code == 201
    body = response.json()
    assert body['media_id'] == str(image.id)

    single = (await client.get(f"/api/news/{body['id']}")).json()
    listed = (await client.get('/api/news')).json()['data'][0]
    assert single['media_id'] == str(image.id)
    assert listed['media_id'] == str(image.id)


async def test_create_rejects_non_image_media(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    """Документ не может быть главным изображением новости."""
    document = await seed_file(fake_repository, fake_storage, name='Договор')

    response = await create_news(client, media_id=str(document.id))

    assert response.status_code == 400
    assert 'изображение' in response.json()['detail']


async def test_create_rejects_unknown_media(client: AsyncClient):
    missing = uuid4()

    response = await create_news(client, media_id=str(missing))

    assert response.status_code == 400
    assert str(missing) in response.json()['detail']


async def test_update_sets_image_media(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    image = await seed_file(fake_repository, fake_storage, file_type=EFileType.JPEG)
    news_id = (await create_news(client)).json()['id']

    response = await client.patch(f'/api/news/{news_id}', json={'media_id': str(image.id)})

    assert response.status_code == 200
    assert response.json()['media_id'] == str(image.id)


async def test_update_clears_media_with_explicit_null(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    """Явный `media_id: null` снимает обложку; отсутствие поля оставляет её как есть."""
    image = await seed_file(fake_repository, fake_storage, file_type=EFileType.AVIF)
    news_id = (await create_news(client, media_id=str(image.id))).json()['id']

    renamed = await client.patch(f'/api/news/{news_id}', json={'name': 'Новое имя'})
    assert renamed.status_code == 200
    assert renamed.json()['media_id'] == str(image.id)

    cleared = await client.patch(f'/api/news/{news_id}', json={'media_id': None})
    assert cleared.status_code == 200
    assert cleared.json()['media_id'] is None
    assert (await client.get(f'/api/news/{news_id}')).json()['media_id'] is None


async def test_update_rejects_non_image_media(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    document = await seed_file(fake_repository, fake_storage, file_type=EFileType.PDF)
    news_id = (await create_news(client)).json()['id']

    response = await client.patch(f'/api/news/{news_id}', json={'media_id': str(document.id)})

    assert response.status_code == 400
    assert (await client.get(f'/api/news/{news_id}')).json()['media_id'] is None


async def test_deleting_media_file_clears_news_media(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    """Удалённый файл не должен оставаться media_id новости."""
    image = await seed_file(fake_repository, fake_storage, file_type=EFileType.WEBP)
    news_id = (await create_news(client, media_id=str(image.id))).json()['id']

    assert (await client.delete(f'/api/files/{image.id}')).status_code == 204

    assert (await client.get(f'/api/news/{news_id}')).json()['media_id'] is None


async def test_list_is_ordered_by_weight(client: AsyncClient):
    for name in ('Первый', 'Второй', 'Третий'):
        await create_news(client, name=name)

    body = (await client.get('/api/news')).json()

    assert body['count'] == 3
    assert [item['name'] for item in body['data']] == ['Первый', 'Второй', 'Третий']
    assert [item['weight'] for item in body['data']] == [0, 1, 2]


async def test_list_filters_and_pagination(client: AsyncClient):
    for name in ('Стол', 'Стул', 'Шкаф'):
        await create_news(client, name=name)

    by_name = await client.get('/api/news', params={'name': 'сту'})
    assert [item['name'] for item in by_name.json()['data']] == ['Стул']

    from_weight = await client.get('/api/news', params={'weight_from': 1})
    assert [item['name'] for item in from_weight.json()['data']] == ['Стул', 'Шкаф']

    to_weight = await client.get('/api/news', params={'weight_to': 1})
    assert [item['name'] for item in to_weight.json()['data']] == ['Стол', 'Стул']

    page = (await client.get('/api/news', params={'page': 2, 'page_size': 2})).json()
    assert page['offset'] == 2
    assert len(page['data']) == 1


async def test_get_news_by_id(client: AsyncClient):
    news_id = (await create_news(client, name='Витрина')).json()['id']

    response = await client.get(f'/api/news/{news_id}')

    assert response.status_code == 200
    assert response.json()['id'] == news_id


async def test_get_unknown_news_returns_404(client: AsyncClient):
    response = await client.get(f'/api/news/{uuid4()}')

    assert response.status_code == 404


async def test_news_hides_service_fields(client: AsyncClient):
    """У новости нет created_at и вложенных файлов — только собственные поля."""
    news_id = (await create_news(client, name='Витрина')).json()['id']

    single = (await client.get(f'/api/news/{news_id}')).json()
    listed = (await client.get('/api/news')).json()['data'][0]

    for news in (single, listed):
        assert set(news) == {'id', 'name', 'description', 'weight', 'media_id'}


async def test_update_name_and_description(client: AsyncClient):
    news_id = (await create_news(client)).json()['id']

    response = await client.patch(
        f'/api/news/{news_id}',
        json={'name': 'Новое имя', 'description': 'Новое описание'},
    )

    assert response.status_code == 200
    assert response.json()['name'] == 'Новое имя'
    assert response.json()['description'] == 'Новое описание'


async def test_update_rejects_negative_weight(client: AsyncClient):
    news_id = (await create_news(client)).json()['id']

    response = await client.patch(f'/api/news/{news_id}', json={'weight': -1})

    assert response.status_code == 422


async def test_update_weight_shifts_other_news(client: AsyncClient):
    news_ids = [
        (await create_news(client, name=name)).json()['id']
        for name in ('Первый', 'Второй', 'Третий')
    ]

    response = await client.patch(f'/api/news/{news_ids[2]}', json={'weight': 1})

    assert response.status_code == 200
    listing = (await client.get('/api/news')).json()['data']
    assert [(item['name'], item['weight']) for item in listing] == [
        ('Первый', 0),
        ('Третий', 1),
        ('Второй', 2),
    ]


async def test_delete_removes_news_but_keeps_files(
    client: AsyncClient, fake_repository: FakeFilesRepository, fake_storage: FakeFileStorage
):
    file = await seed_file(fake_repository, fake_storage)
    news_id = (await create_news(client)).json()['id']

    response = await client.delete(f'/api/news/{news_id}')

    assert response.status_code == 204
    assert (await client.get(f'/api/news/{news_id}')).status_code == 404
    assert (await client.get('/api/news')).json()['count'] == 0
    # файлы живут отдельно от новостей: удаление новости их не трогает
    assert (await client.get(f'/api/files/{file.id}/download')).status_code == 200


async def test_delete_unknown_news_returns_404(client: AsyncClient):
    response = await client.delete(f'/api/news/{uuid4()}')

    assert response.status_code == 404


async def test_delete_recounts_weights(client: AsyncClient):
    for name in ('Первый', 'Второй', 'Третий'):
        await create_news(client, name=name)
    second_id = (await client.get('/api/news', params={'name': 'Второй'})).json()['data'][0]['id']

    response = await client.delete(f'/api/news/{second_id}')

    assert response.status_code == 204
    listing = (await client.get('/api/news')).json()['data']
    assert [(item['name'], item['weight']) for item in listing] == [
        ('Первый', 0),
        ('Третий', 1),
    ]


async def test_create_after_delete_takes_last_weight(client: AsyncClient):
    for name in ('Первый', 'Второй', 'Третий'):
        await create_news(client, name=name)
    second_id = (await client.get('/api/news', params={'name': 'Второй'})).json()['data'][0]['id']
    await client.delete(f'/api/news/{second_id}')

    response = await create_news(client, name='Четвёртый')

    assert response.json()['weight'] == 2


async def test_update_rejects_weight_outside_list(client: AsyncClient):
    last_id = None
    for name in ('Первый', 'Второй', 'Третий'):
        last_id = (await create_news(client, name=name)).json()['id']

    # последняя в списке не может «добавить себе вес» — позиции идут подряд: 0, 1, 2
    response = await client.patch(f'/api/news/{last_id}', json={'weight': 3})

    assert response.status_code == 400
    assert 'Вес не может быть больше 2' in response.json()['detail']
    assert (await client.get('/api/news')).json()['data'][2]['weight'] == 2


async def test_update_weight_keeps_sequence_continuous(client: AsyncClient):
    ids = {
        name: (await create_news(client, name=name)).json()['id']
        for name in ('Первый', 'Второй', 'Третий', 'Четвёртый')
    }

    # перенос первой в конец не должен оставлять пропуск на прежнем месте
    response = await client.patch(f'/api/news/{ids["Первый"]}', json={'weight': 3})

    assert response.status_code == 200
    listing = (await client.get('/api/news')).json()['data']
    assert [(item['name'], item['weight']) for item in listing] == [
        ('Второй', 0),
        ('Третий', 1),
        ('Четвёртый', 2),
        ('Первый', 3),
    ]


async def test_delete_many_removes_news(
    client: AsyncClient,
    fake_news_repository: FakeNewsRepository,
):
    first = (await create_news(client, name='Первый')).json()
    second = (await create_news(client, name='Второй')).json()

    await fake_news_repository.delete_many(pks=[UUID(first['id']), UUID(second['id'])])

    assert fake_news_repository.items == {}
    assert (await client.get('/api/news')).json()['count'] == 0


async def test_delete_many_unknown_news_keeps_records(
    fake_news_repository: FakeNewsRepository,
):
    news = await fake_news_repository.create_one(data=NewsCreateSchema(name='Товар'))

    with pytest.raises(ObjectNotFoundException):
        await fake_news_repository.delete_many(pks=[news.id, uuid4()])

    assert news.id in fake_news_repository.items


async def test_client_role_forbidden_for_mutations(
    client_as_client: AsyncClient, fake_news_repository: FakeNewsRepository
):
    news = await fake_news_repository.create_one(data=NewsCreateSchema(name='Товар'))

    create_response = await create_news(client_as_client)
    update_response = await client_as_client.patch(
        f'/api/news/{news.id}', json={'name': 'Другое'}
    )
    delete_response = await client_as_client.delete(f'/api/news/{news.id}')

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_read_endpoints_are_public():
    """GET новостей доступны без токена, мутации — под bearer-схемой."""
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()['paths']

    listing = paths['/api/news']['get']
    single = paths['/api/news/{news_id}']['get']
    mutations = (
        paths['/api/news']['post'],
        paths['/api/news/{news_id}']['patch'],
        paths['/api/news/{news_id}']['delete'],
    )

    assert 'security' not in listing
    assert 'security' not in single
    assert all('security' in method for method in mutations)


async def test_client_role_can_read_news(
    client_as_client: AsyncClient, fake_news_repository: FakeNewsRepository
):
    news = await fake_news_repository.create_one(data=NewsCreateSchema(name='Товар'))

    listing = await client_as_client.get('/api/news')
    single = await client_as_client.get(f'/api/news/{news.id}')

    assert listing.status_code == 200
    assert listing.json()['count'] == 1
    assert single.status_code == 200
    assert single.json()['name'] == 'Товар'
