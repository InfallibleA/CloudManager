from uuid import UUID

import pytest
from httpx import AsyncClient

from app.auth.security import create_access_token
from app.auth.service.auth import AuthService
from app.core.enums import EUserRole
from app.core.exceptions import ForbiddenException
from app.users.schema.users import UserCreateInternalSchema
from app.users.service.users import UsersService
from tests.conftest import build_test_settings
from tests.fakes import FakeFoldersRepository, FakeUsersRepository

REGISTER_URL = '/api/auth/register'
LOGIN_URL = '/api/auth/login'
USERS_URL = '/api/auth/users'

NEW_USER = {'login': 'newuser', 'password': 'secret-password'}


async def create_fake_user(
    fake_users_repository: FakeUsersRepository, *, login: str, role: EUserRole
) -> None:
    """Кладёт пользователя прямо в фейковый репозиторий, минуя регистрацию."""
    await fake_users_repository.create_one(
        data=UserCreateInternalSchema(login=login, password_hash='hash', role=role)
    )


async def test_register_creates_client(
    client_without_token: AsyncClient, fake_users_repository: FakeUsersRepository
):
    """Регистрация открыта без токена и создаёт пользователя с ролью client."""
    response = await client_without_token.post(REGISTER_URL, json=NEW_USER)

    assert response.status_code == 201
    body = response.json()
    assert body['login'] == NEW_USER['login']
    assert body['role'] == EUserRole.CLIENT.value
    assert body['id'] and body['created_at']
    # пароль наружу не отдаётся
    assert 'password' not in body and 'password_hash' not in body

    stored = list(fake_users_repository.credentials.values())
    assert len(stored) == 1
    assert stored[0].password_hash != NEW_USER['password']


async def test_register_creates_root_folder(
    client_without_token: AsyncClient, fake_folders_repository: FakeFoldersRepository
):
    """Вместе с пользователем создаётся его корневая папка — от неё строится дерево."""
    response = await client_without_token.post(REGISTER_URL, json=NEW_USER)

    user_id = UUID(response.json()['id'])
    fake_folders_repository.use_owner(owner_id=user_id)
    root = await fake_folders_repository.get_root()

    assert root is not None
    assert root.is_root is True
    assert root.parent_id is None
    assert root.name == NEW_USER['login']
    # владелец корневой папки — сам зарегистрированный пользователь, а не ROOT_USER
    assert fake_folders_repository.creators[root.id] == user_id


async def test_register_rejects_duplicate_login(client_without_token: AsyncClient):
    """Повторный логин не регистрируется: нарушение уникальности."""
    assert (await client_without_token.post(REGISTER_URL, json=NEW_USER)).status_code == 201

    response = await client_without_token.post(REGISTER_URL, json=NEW_USER)

    assert response.status_code == 400


async def test_register_validates_credentials(client_without_token: AsyncClient):
    """Логин короче 3 и пароль короче 8 символов отклоняются схемой."""
    response = await client_without_token.post(
        REGISTER_URL, json={'login': 'ab', 'password': 'short'}
    )

    assert response.status_code == 422


async def test_registered_user_can_login(
    client_without_token: AsyncClient, fake_users_repository: FakeUsersRepository
):
    """После регистрации выданные учётные данные подходят для входа."""
    await client_without_token.post(REGISTER_URL, json=NEW_USER)

    response = await client_without_token.post(LOGIN_URL, json=NEW_USER)

    assert response.status_code == 200
    body = response.json()
    assert body['access_token']
    assert body['token_type'] == 'Bearer'
    assert body['expires_in'] > 0


async def test_users_list_requires_admin(
    client_as_client: AsyncClient, client_without_token: AsyncClient
):
    """Список пользователей доступен только администратору."""
    assert (await client_without_token.get(USERS_URL)).status_code == 401
    assert (await client_as_client.get(USERS_URL)).status_code == 403


async def test_users_list_filters_and_paginates(
    client: AsyncClient, fake_users_repository: FakeUsersRepository
):
    """Список фильтруется по логину и роли и отдаётся постранично."""
    await create_fake_user(fake_users_repository, login='alice', role=EUserRole.CLIENT)
    await create_fake_user(fake_users_repository, login='alex', role=EUserRole.ADMIN)
    await create_fake_user(fake_users_repository, login='bob', role=EUserRole.CLIENT)

    response = await client.get(USERS_URL, params={'login': 'AL', 'role': 'admin'})

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 1
    assert body['offset'] == 0
    assert [user['login'] for user in body['data']] == ['alex']

    response = await client.get(USERS_URL, params={'page': 2, 'page_size': 2})

    body = response.json()
    assert body['count'] == 3
    assert body['offset'] == 2
    assert body['page'] == 2
    assert body['page_size'] == 2
    assert [user['login'] for user in body['data']] == ['bob']


async def test_users_list_validates_role(client: AsyncClient):
    """Неизвестная роль отклоняется на уровне схемы."""
    assert (await client.get(USERS_URL, params={'role': 'root'})).status_code == 422


async def test_admin_blocks_and_unblocks_user(
    client: AsyncClient, client_without_token: AsyncClient
):
    """Блокировка запрещает вход, разблокировка возвращает доступ."""
    registered = (await client_without_token.post(REGISTER_URL, json=NEW_USER)).json()
    user_id = registered['id']

    blocked = await client.post(f'{USERS_URL}/{user_id}/block')

    assert blocked.status_code == 200
    assert blocked.json()['is_blocked'] is True

    denied = await client_without_token.post(LOGIN_URL, json=NEW_USER)
    assert denied.status_code == 403
    assert denied.json()['detail'] == 'Пользователь заблокирован.'

    listed = await client.get(USERS_URL, params={'login': NEW_USER['login']})
    assert listed.json()['data'][0]['is_blocked'] is True

    unblocked = await client.post(f'{USERS_URL}/{user_id}/unblock')

    assert unblocked.status_code == 200
    assert unblocked.json()['is_blocked'] is False
    assert (await client_without_token.post(LOGIN_URL, json=NEW_USER)).status_code == 200


async def test_block_requires_admin(
    client_as_client: AsyncClient,
    client_without_token: AsyncClient,
    fake_users_repository: FakeUsersRepository,
):
    """Блокировать пользователей может только администратор."""
    user = await fake_users_repository.create_one(
        data=UserCreateInternalSchema(login='blocked', password_hash='hash')
    )

    assert (
        await client_without_token.post(f'{USERS_URL}/{user.id}/block')
    ).status_code == 401
    assert (await client_as_client.post(f'{USERS_URL}/{user.id}/block')).status_code == 403


async def test_authenticate_rejects_blocked_user(
    fake_users_repository: FakeUsersRepository,
    fake_folders_repository: FakeFoldersRepository,
):
    """Ранее выданный токен заблокированного пользователя не пускает в API."""
    user = await fake_users_repository.create_one(
        data=UserCreateInternalSchema(login='blocked', password_hash='hash')
    )
    await fake_users_repository.set_blocked(pk=user.id, blocked=True)
    config = build_test_settings()
    auth_service = AuthService(
        users_service=UsersService(users_repository=fake_users_repository),
        folders_repository=fake_folders_repository,
        config=config,
    )
    token, _ = create_access_token(user_id=user.id, config=config)

    with pytest.raises(ForbiddenException) as err:
        await auth_service.authenticate(token=token)

    assert err.value.detail == 'Пользователь заблокирован.'
