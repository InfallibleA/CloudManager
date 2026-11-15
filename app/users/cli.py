"""CLI управления пользователями.

Запуск:
    python -m app.users.cli create-admin

Скрипт запрашивает логин и пароль в консоли и создаёт администратора
от лица ROOT_USER. Саморегистрации через API нет: пользователи создаются
только этой командой, и только с ролью admin.
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError

from app.auth.service.auth import AuthService
from app.config import settings
from app.core.context import Context
from app.core.engines.database import Transaction
from app.core.exceptions import BaseOrderException
from app.folders.repository.folders import FoldersRepository
from app.users.repository.users import UsersRepository
from app.users.schema.users import UserCreateSchema, UserResponseSchema
from app.users.service.users import UsersService

CREATE_ADMIN = 'create-admin'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog='python -m app.users.cli', description='Управление пользователями cloud_manager'
    )
    commands = parser.add_subparsers(dest='command', required=True)

    create_admin_parser = commands.add_parser(CREATE_ADMIN, help='Создать администратора')
    create_admin_parser.add_argument(
        '--login', help='Логин администратора; если не указан, будет запрошен в консоли'
    )

    return parser.parse_args(argv)


def read_credentials(login: str | None = None) -> UserCreateSchema:
    """Запрашивает логин и пароль в консоли (пароль не отображается)."""
    login = (login or input('Логин: ')).strip()
    password = getpass.getpass('Пароль: ')
    password_repeat = getpass.getpass('Повторите пароль: ')

    if password != password_repeat:
        raise ValueError('Пароли не совпадают.')

    return UserCreateSchema(login=login, password=password)


async def create_admin(data: UserCreateSchema) -> UserResponseSchema:
    """Создаёт администратора в БД."""
    transaction = Transaction()
    try:
        users_service = UsersService(
            users_repository=UsersRepository(transaction=transaction, context=Context())
        )
        auth_service = AuthService(
            users_service=users_service,
            folders_repository=FoldersRepository(
                transaction=transaction, context=Context()
            ),
            config=settings,
        )
        return await auth_service.create_admin(data=data)
    finally:
        await transaction.engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI. Возвращает код возврата процесса."""
    args = parse_args(argv)

    try:
        data = read_credentials(args.login)
        user = asyncio.run(create_admin(data=data))
    except (ValueError, BaseOrderException) as err:
        print(f'Ошибка: {_error_message(err)}', file=sys.stderr)
        return 1

    print(f'Администратор создан: {user.login} (id={user.id}, роль={user.role.value})')
    return 0


def _error_message(err: Exception) -> str:
    if isinstance(err, ValidationError):
        return '; '.join(f'{error["loc"][0]}: {error["msg"]}' for error in err.errors())
    return str(getattr(err, 'detail', err))


if __name__ == '__main__':
    raise SystemExit(main())
