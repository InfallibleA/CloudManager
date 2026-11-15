import getpass
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.users.cli as cli
from app.core.enums import EUserRole
from app.core.exceptions import UniqueConstraintException
from app.users.cli import CREATE_ADMIN
from app.users.schema.users import UserCreateSchema, UserResponseSchema

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_parse_args_reads_login():
    args = cli.parse_args([CREATE_ADMIN, '--login', 'admin'])

    assert args.command == CREATE_ADMIN
    assert args.login == 'admin'


def test_parse_args_requires_command():
    with pytest.raises(SystemExit):
        cli.parse_args([])


def test_read_credentials_uses_login_argument(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(getpass, 'getpass', lambda prompt='': 'secret-password')

    data = cli.read_credentials('admin')

    assert data.login == 'admin'
    assert data.password == 'secret-password'


def test_read_credentials_asks_login(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('builtins.input', lambda prompt='': '  admin  ')
    monkeypatch.setattr(getpass, 'getpass', lambda prompt='': 'secret-password')

    assert cli.read_credentials().login == 'admin'


def test_read_credentials_rejects_password_mismatch(monkeypatch: pytest.MonkeyPatch):
    answers = iter(['secret-password', 'other-password'])
    monkeypatch.setattr('builtins.input', lambda prompt='': 'admin')
    monkeypatch.setattr(getpass, 'getpass', lambda prompt='': next(answers))

    with pytest.raises(ValueError, match='Пароли не совпадают'):
        cli.read_credentials()


def test_read_credentials_validates_login(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('builtins.input', lambda prompt='': 'ab')
    monkeypatch.setattr(getpass, 'getpass', lambda prompt='': 'secret-password')

    with pytest.raises(ValidationError):
        cli.read_credentials()


def make_user(login: str) -> UserResponseSchema:
    return UserResponseSchema(
        id=uuid4(), login=login, role=EUserRole.ADMIN, created_at=datetime.now(timezone.utc)
    )


def stub_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('builtins.input', lambda prompt='': 'admin')
    monkeypatch.setattr(getpass, 'getpass', lambda prompt='': 'secret-password')


def test_main_reports_created_admin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    async def create_admin(*, data: UserCreateSchema) -> UserResponseSchema:
        return make_user(data.login)

    stub_credentials(monkeypatch)
    monkeypatch.setattr(cli, 'create_admin', create_admin)

    exit_code = cli.main([CREATE_ADMIN])

    assert exit_code == 0
    assert 'Администратор создан: admin' in capsys.readouterr().out


def test_main_reports_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    async def create_admin(*, data: UserCreateSchema) -> UserResponseSchema:
        raise UniqueConstraintException(fields=['login'])

    stub_credentials(monkeypatch)
    monkeypatch.setattr(cli, 'create_admin', create_admin)

    exit_code = cli.main([CREATE_ADMIN])

    assert exit_code == 1
    assert 'Поле login должны быть уникальны' in capsys.readouterr().err


def test_users_models_configure_without_files_module():
    """CLI импортирует только users, поэтому мапперы должны собираться без files."""
    script = (
        'from sqlalchemy.orm import configure_mappers;'
        ' import app.users.repository.users;'
        ' configure_mappers();'
        ' print("ok")'
    )

    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert 'ok' in result.stdout
