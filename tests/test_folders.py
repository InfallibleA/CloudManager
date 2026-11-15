from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from app.routers import router
from tests.conftest import ADMIN_USER_ID, CLIENT_USER_ID
from tests.fakes import (
    FakeFilesRepository,
    FakeFileStorage,
    FakeFoldersRepository,
    seed_file,
    seed_folder,
)


async def create_folder(
    client: AsyncClient,
    *,
    name: str = 'Документы',
    parent_id=None,
    file_ids: list | None = None,
):
    """Создаёт папку через REST так же, как это делает фронтенд."""
    payload: dict = {
        'name': name,
        'file_ids': [str(file_id) for file_id in file_ids or []],
    }
    if parent_id is not None:
        payload['parent_id'] = str(parent_id)
    return await client.post('/api/folders', json=payload)


async def seed_root(
    repository: FakeFoldersRepository, *, owner_id: UUID, name: str = 'Мои файлы'
):
    """Кладёт корневую папку — как её создаёт регистрация пользователя."""
    return await repository.create_root(owner_id=owner_id, name=name)


async def test_create_folder(client: AsyncClient):
    response = await create_folder(client)

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Документы'
    assert body['parent_id'] is None
    assert body['files'] == []
    assert body['children'] == []
    assert body['id']


async def test_create_folder_records_current_user_as_creator(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """creator_id — тот, кто создал папку, а не служебный ROOT_USER."""
    folder_id = (await create_folder(client)).json()['id']

    assert fake_folders_repository.creators[UUID(folder_id)] == ADMIN_USER_ID


async def test_create_folder_by_client_records_him_as_creator(
    client_as_client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    folder_id = (await create_folder(client_as_client, name='Мои файлы')).json()['id']

    assert fake_folders_repository.creators[UUID(folder_id)] == CLIENT_USER_ID


async def test_create_nested_folder(client: AsyncClient):
    parent_id = (await create_folder(client, name='Проекты')).json()['id']

    nested = (await create_folder(client, name='Сметы', parent_id=parent_id)).json()

    assert nested['parent_id'] == parent_id
    parent = (await client.get(f'/api/folders/{parent_id}')).json()
    assert [child['name'] for child in parent['children']] == ['Сметы']


async def test_list_supports_filters_and_pagination(client: AsyncClient):
    root_id = (await create_folder(client, name='Проекты')).json()['id']
    await create_folder(client, name='Сметы', parent_id=root_id)
    await create_folder(client, name='Договоры')

    all_folders = (await client.get('/api/folders')).json()
    assert all_folders['count'] == 3
    assert all_folders['page'] == 1
    assert all_folders['page_size'] == 25

    only_root = (await client.get('/api/folders', params={'root_only': 'true'})).json()
    assert sorted(item['name'] for item in only_root['data']) == ['Договоры', 'Проекты']

    inside = (await client.get('/api/folders', params={'parent_id': root_id})).json()
    assert [item['name'] for item in inside['data']] == ['Сметы']

    by_name = (await client.get('/api/folders', params={'name': 'смет'})).json()
    assert [item['name'] for item in by_name['data']] == ['Сметы']

    page = (await client.get('/api/folders', params={'page': 2, 'page_size': 2})).json()
    assert page['count'] == 3
    assert page['offset'] == 2
    assert len(page['data']) == 1


async def test_admin_filters_folders_by_creator(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Админ может запросить папки конкретного пользователя через `creator_id`."""
    await create_folder(client, name='Папка админа')
    await seed_folder(fake_folders_repository, name='Чужая', creator_id=CLIENT_USER_ID)

    own = (await client.get('/api/folders', params={'creator_id': str(ADMIN_USER_ID)})).json()
    foreign = (
        await client.get('/api/folders', params={'creator_id': str(CLIENT_USER_ID)})
    ).json()

    assert [item['name'] for item in own['data']] == ['Папка админа']
    assert [item['name'] for item in foreign['data']] == ['Чужая']


async def test_client_creator_filter_does_not_reveal_foreign_folders(
    client: AsyncClient, client_as_client: AsyncClient
):
    """Не-админ с чужим `creator_id` получает пустой список, а не чужие папки."""
    await create_folder(client, name='Папка админа')
    await create_folder(client_as_client, name='Папка клиента')

    foreign = (
        await client_as_client.get('/api/folders', params={'creator_id': str(ADMIN_USER_ID)})
    ).json()
    own = (
        await client_as_client.get('/api/folders', params={'creator_id': str(CLIENT_USER_ID)})
    ).json()

    assert foreign['count'] == 0
    assert foreign['data'] == []
    assert [item['name'] for item in own['data']] == ['Папка клиента']


async def test_creator_filter_rejects_invalid_uuid(client: AsyncClient):
    response = await client.get('/api/folders', params={'creator_id': 'not-a-uuid'})

    assert response.status_code == 422


async def test_create_folder_with_files(
    client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_folders_repository: FakeFoldersRepository,
    fake_storage: FakeFileStorage,
):
    file = await seed_file(fake_repository, fake_storage, name='Договор')

    body = (await create_folder(client, file_ids=[file.id])).json()

    assert [item['id'] for item in body['files']] == [str(file.id)]
    # связь папки с файлом знает, кто именно её создал
    assert fake_folders_repository.file_creators[(UUID(body['id']), file.id)] == ADMIN_USER_ID


async def test_folder_content_has_created_at(
    client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Дата есть у самой папки, а также у файлов и подпапок в её содержимом."""
    file = await seed_file(fake_repository, fake_storage, name='Договор')
    folder = (await create_folder(client, name='Проекты', file_ids=[file.id])).json()
    await create_folder(client, name='Сметы', parent_id=folder['id'])

    body = (await client.get(f"/api/folders/{folder['id']}")).json()

    assert body['created_at']
    assert body['files'][0]['created_at']
    assert body['children'][0]['created_at']


async def test_update_replaces_files(client: AsyncClient, fake_repository, fake_storage):
    first = await seed_file(fake_repository, fake_storage, name='Первый')
    second = await seed_file(fake_repository, fake_storage, name='Второй')
    folder_id = (await create_folder(client, file_ids=[first.id])).json()['id']

    body = (
        await client.patch(f'/api/folders/{folder_id}', json={'file_ids': [str(second.id)]})
    ).json()

    assert [item['name'] for item in body['files']] == ['Второй']


async def test_update_renames_and_moves_folder(client: AsyncClient):
    first_id = (await create_folder(client, name='Проекты')).json()['id']
    second_id = (await create_folder(client, name='Архив')).json()['id']

    body = (
        await client.patch(
            f'/api/folders/{second_id}', json={'name': 'Архив 2026', 'parent_id': str(first_id)}
        )
    ).json()

    assert body['name'] == 'Архив 2026'
    assert body['parent_id'] == first_id


async def test_update_without_parent_keeps_it(client: AsyncClient):
    parent_id = (await create_folder(client, name='Проекты')).json()['id']
    child_id = (await create_folder(client, name='Сметы', parent_id=parent_id)).json()['id']

    body = (await client.patch(f'/api/folders/{child_id}', json={'name': 'Сметы 2026'})).json()

    assert body['parent_id'] == parent_id


async def test_update_moves_folder_back_to_root(client: AsyncClient):
    parent_id = (await create_folder(client, name='Проекты')).json()['id']
    child_id = (await create_folder(client, name='Сметы', parent_id=parent_id)).json()['id']

    body = (
        await client.patch(f'/api/folders/{child_id}', json={'parent_id': None})
    ).json()

    assert body['parent_id'] is None


async def test_folder_without_parent_goes_into_root_folder(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Без `parent_id` папка создаётся внутри корневой папки пользователя."""
    root = await seed_root(fake_folders_repository, owner_id=ADMIN_USER_ID)

    body = (await create_folder(client, name='Проекты')).json()

    assert body['parent_id'] == str(root.id)
    assert body['is_root'] is False


async def test_root_folder_is_listed_with_flag(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Корневую папку видно в `root_only`: по флагу клиент находит точку входа."""
    root = await seed_root(fake_folders_repository, owner_id=ADMIN_USER_ID)

    body = (await client.get('/api/folders', params={'root_only': 'true'})).json()

    assert body['count'] == 1
    assert body['data'][0]['id'] == str(root.id)
    assert body['data'][0]['is_root'] is True


async def test_update_moves_folder_into_root_folder(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """`parent_id: null` возвращает папку в корневую папку пользователя."""
    root = await seed_root(fake_folders_repository, owner_id=ADMIN_USER_ID)
    parent_id = (await create_folder(client, name='Проекты')).json()['id']
    child_id = (await create_folder(client, name='Сметы', parent_id=parent_id)).json()['id']

    body = (
        await client.patch(f'/api/folders/{child_id}', json={'parent_id': None})
    ).json()

    assert body['parent_id'] == str(root.id)


async def test_root_folder_cannot_be_deleted(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Без корневой папки пользователю некуда класть файлы — удаление запрещено."""
    root = await seed_root(fake_folders_repository, owner_id=ADMIN_USER_ID)

    response = await client.delete(f'/api/folders/{root.id}')

    assert response.status_code == 400
    assert (await client.get(f'/api/folders/{root.id}')).status_code == 200


async def test_root_folder_cannot_be_moved(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Корневая папка остаётся верхним уровнем своего дерева."""
    root = await seed_root(fake_folders_repository, owner_id=ADMIN_USER_ID)
    other_id = (await create_folder(client, name='Проекты')).json()['id']

    response = await client.patch(f'/api/folders/{root.id}', json={'parent_id': other_id})

    assert response.status_code == 400


async def test_create_rejects_unknown_parent(client: AsyncClient):
    response = await create_folder(client, parent_id=uuid4())

    assert response.status_code == 400
    assert 'Папка не найдена' in response.json()['detail']


async def test_create_rejects_unknown_file(client: AsyncClient):
    response = await create_folder(client, file_ids=[uuid4()])

    assert response.status_code == 400
    assert 'Файлы не найдены' in response.json()['detail']


async def test_update_rejects_self_as_parent(client: AsyncClient):
    folder_id = (await create_folder(client)).json()['id']

    response = await client.patch(
        f'/api/folders/{folder_id}', json={'parent_id': str(folder_id)}
    )

    assert response.status_code == 400
    assert response.json()['detail'] == 'Папка не может быть родителем самой себя.'


async def test_update_rejects_move_into_own_subfolder(client: AsyncClient):
    parent_id = (await create_folder(client, name='Проекты')).json()['id']
    child_id = (await create_folder(client, name='Сметы', parent_id=parent_id)).json()['id']
    grandchild_id = (
        await create_folder(client, name='2026', parent_id=child_id)
    ).json()['id']

    response = await client.patch(
        f'/api/folders/{parent_id}', json={'parent_id': str(grandchild_id)}
    )

    assert response.status_code == 400
    assert response.json()['detail'] == 'Нельзя переместить папку внутрь её подпапки.'


async def test_update_rejects_unknown_folder(client: AsyncClient):
    response = await client.patch(f'/api/folders/{uuid4()}', json={'name': 'Новая'})

    assert response.status_code == 404


async def test_get_unknown_folder_returns_404(client: AsyncClient):
    assert (await client.get(f'/api/folders/{uuid4()}')).status_code == 404


async def test_delete_removes_folder_with_subfolders_and_files(
    client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Удаление папки уносит подпапки и файлы внутри них — включая объекты из хранилища."""
    folder_id = (await create_folder(client, name='Проекты')).json()['id']
    child_id = (await create_folder(client, name='Сметы', parent_id=folder_id)).json()['id']
    root_file = await seed_file(fake_repository, fake_storage, name='В корне')
    nested_file = await seed_file(fake_repository, fake_storage, name='В подпапке')
    await client.patch(f'/api/folders/{folder_id}', json={'file_ids': [str(root_file.id)]})
    await client.patch(f'/api/folders/{child_id}', json={'file_ids': [str(nested_file.id)]})

    response = await client.delete(f'/api/folders/{folder_id}')

    assert response.status_code == 204
    assert (await client.get('/api/folders')).json()['count'] == 0
    assert fake_repository.items == {}
    assert fake_storage.objects == {}
    assert (await client.get(f'/api/files/{root_file.id}/download')).status_code == 404
    assert (await client.get(f'/api/files/{nested_file.id}/download')).status_code == 404


async def test_delete_unknown_folder_returns_404(client: AsyncClient):
    assert (await client.delete(f'/api/folders/{uuid4()}')).status_code == 404


async def test_file_deleted_from_files_module_leaves_folder(
    client: AsyncClient,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Файл, удалённый через /api/files, исчезает и из выдачи папки."""
    file = await seed_file(fake_repository, fake_storage, name='Договор')
    folder_id = (await create_folder(client, file_ids=[file.id])).json()['id']

    await client.delete(f'/api/files/{file.id}')

    assert (await client.get(f'/api/folders/{folder_id}')).json()['files'] == []


async def test_admin_has_full_access_to_foreign_folder(
    client: AsyncClient,
    fake_folders_repository: FakeFoldersRepository,
    fake_repository: FakeFilesRepository,
    fake_storage: FakeFileStorage,
):
    """Админ открывает, переименовывает и удаляет папку другого пользователя."""
    file = await seed_file(fake_repository, fake_storage, name='Договор')
    foreign = await seed_folder(
        fake_folders_repository,
        name='Чужая',
        file_ids=[file.id],
        creator_id=CLIENT_USER_ID,
    )

    single = await client.get(f'/api/folders/{foreign.id}')

    assert single.status_code == 200
    body = single.json()
    assert body['name'] == 'Чужая'
    assert [item['name'] for item in body['files']] == ['Договор']

    renamed = await client.patch(f'/api/folders/{foreign.id}', json={'name': 'Переименована'})
    assert renamed.status_code == 200
    assert renamed.json()['name'] == 'Переименована'

    deleted = await client.delete(f'/api/folders/{foreign.id}')
    assert deleted.status_code == 204
    assert foreign.id not in fake_folders_repository.items


async def test_foreign_folder_is_invisible_for_client(
    client_as_client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Папки другого пользователя не видны клиенту: их просто нет в выборках."""
    foreign = await seed_folder(
        fake_folders_repository, name='Чужая', creator_id=ADMIN_USER_ID
    )

    listing = await client_as_client.get('/api/folders')
    single = await client_as_client.get(f'/api/folders/{foreign.id}')
    delete = await client_as_client.delete(f'/api/folders/{foreign.id}')

    assert listing.json()['count'] == 0
    assert single.status_code == 404
    assert delete.status_code == 404


async def test_admin_moves_foreign_folder_to_owner_root(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """`parent_id: null` возвращает чужую папку в корень её владельца, а не админа."""
    root = await seed_root(
        fake_folders_repository, owner_id=CLIENT_USER_ID, name='Клиент'
    )
    child = await seed_folder(
        fake_folders_repository, name='Дочерняя', creator_id=CLIENT_USER_ID
    )

    response = await client.patch(f'/api/folders/{child.id}', json={'parent_id': None})

    assert response.status_code == 200
    assert response.json()['parent_id'] == str(root.id)


async def test_admin_cannot_move_foreign_folder_into_own_tree(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Перемещение между разными владельцами отклоняется: дерево остаётся цельным."""
    own = await seed_folder(
        fake_folders_repository, name='Своя', creator_id=ADMIN_USER_ID
    )
    foreign = await seed_folder(
        fake_folders_repository, name='Чужая', creator_id=CLIENT_USER_ID
    )

    response = await client.patch(
        f'/api/folders/{foreign.id}', json={'parent_id': str(own.id)}
    )

    assert response.status_code == 400
    assert 'Папка не найдена' in response.json()['detail']


async def test_admin_cannot_delete_or_move_foreign_root(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Корневая папка защищена от удаления и перемещения — даже для админа."""
    root = await seed_root(
        fake_folders_repository, owner_id=CLIENT_USER_ID, name='Клиент'
    )

    deleted = await client.delete(f'/api/folders/{root.id}')
    moved = await client.patch(f'/api/folders/{root.id}', json={'parent_id': None})

    assert deleted.status_code == 400
    assert deleted.json()['detail'] == 'Корневую папку удалить нельзя.'
    assert moved.status_code == 400
    assert moved.json()['detail'] == 'Корневую папку нельзя переместить.'


async def test_each_user_sees_only_his_folders(
    client: AsyncClient, client_as_client: AsyncClient
):
    """Один и тот же API отдаёт каждому пользователю только его папки."""
    await create_folder(client, name='Папка админа')

    assert (await client.get('/api/folders')).json()['count'] == 1
    assert (await client_as_client.get('/api/folders')).json()['count'] == 0


async def test_foreign_folder_cannot_be_used_as_parent(
    client: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    foreign = await seed_folder(
        fake_folders_repository, name='Чужая', creator_id=CLIENT_USER_ID
    )

    response = await create_folder(client, parent_id=foreign.id)

    assert response.status_code == 400
    assert 'Папка не найдена' in response.json()['detail']


async def test_folders_need_token(client_without_token: AsyncClient):
    """Папки доступны только зарегистрированным пользователям."""
    folder_id = uuid4()

    assert (await create_folder(client_without_token)).status_code == 401
    assert (await client_without_token.get('/api/folders')).status_code == 401
    assert (await client_without_token.get(f'/api/folders/{folder_id}')).status_code == 401
    assert (
        await client_without_token.patch(f'/api/folders/{folder_id}', json={'name': 'Новая'})
    ).status_code == 401
    assert (await client_without_token.delete(f'/api/folders/{folder_id}')).status_code == 401


def test_openapi_marks_all_folder_endpoints_as_protected():
    """Папки — личное пространство: bearer-схема есть у каждой ручки."""
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()['paths']

    assert all(
        'security' in method
        for method in (
            paths['/api/folders']['get'],
            paths['/api/folders']['post'],
            paths['/api/folders/{folder_id}']['get'],
            paths['/api/folders/{folder_id}']['patch'],
            paths['/api/folders/{folder_id}']['delete'],
        )
    )
