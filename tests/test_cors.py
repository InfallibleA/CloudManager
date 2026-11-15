from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.cors import add_cors_middleware
from tests.conftest import build_test_settings

SITE_ORIGIN = 'https://cloudmanager.ru'
ADMIN_ORIGIN = 'https://admin.cloudmanager.ru'
FOREIGN_ORIGIN = 'https://evil.example'


def build_cors_app(**overrides: Any) -> FastAPI:
    """Мини-приложение с тем же CORS, что и в `app/main.py`."""
    app = FastAPI()
    add_cors_middleware(app, config=build_test_settings(**overrides))

    @app.get('/api/files/{file_id}/download')
    async def download_file() -> dict[str, str]:
        return {'result': 'ok'}

    return app


def call_app(app: FastAPI, *, origin: str, headers: dict[str, str] | None = None) -> AsyncClient:
    """Клиент к приложению, который подставляет домен в заголовок Origin."""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
        headers={'Origin': origin, **(headers or {})},
    )


async def test_preflight_request_from_allowed_origin():
    app = build_cors_app(CORS_ORIGINS=[SITE_ORIGIN])

    async with call_app(
        app,
        origin=SITE_ORIGIN,
        headers={
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'authorization',
        },
    ) as client:
        response = await client.options('/api/files/1/download')

    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == SITE_ORIGIN
    assert 'GET' in response.headers['access-control-allow-methods']
    # фронтенд отправляет Bearer-токен, значит заголовок Authorization должен быть разрешён
    assert 'authorization' in response.headers['access-control-allow-headers'].lower()


async def test_origins_from_env_are_listed_with_comma():
    app = build_cors_app(CORS_ORIGINS=f'{SITE_ORIGIN}, {ADMIN_ORIGIN}')

    async with call_app(app, origin=ADMIN_ORIGIN) as client:
        response = await client.get('/api/files/1/download')

    assert response.headers['access-control-allow-origin'] == ADMIN_ORIGIN


async def test_download_response_exposes_file_name_headers():
    app = build_cors_app(CORS_ORIGINS=['*'])

    async with call_app(app, origin=SITE_ORIGIN) as client:
        response = await client.get('/api/files/1/download')

    assert response.headers['access-control-allow-origin'] == '*'
    # без этих заголовков фронтенд не увидит имя файла при скачивании через fetch
    exposed = response.headers['access-control-expose-headers']
    assert 'Content-Disposition' in exposed


async def test_unknown_origin_gets_no_cors_headers():
    app = build_cors_app(CORS_ORIGINS=[SITE_ORIGIN])

    async with call_app(app, origin=FOREIGN_ORIGIN) as client:
        response = await client.get('/api/files/1/download')

    assert 'access-control-allow-origin' not in response.headers


def test_settings_parse_comma_separated_origins():
    settings = build_test_settings(CORS_ORIGINS=f'{SITE_ORIGIN}, {ADMIN_ORIGIN}')

    assert settings.CORS_ORIGINS == [SITE_ORIGIN, ADMIN_ORIGIN]


def test_settings_reject_wildcard_with_credentials():
    # браузер отклонил бы такой ответ, поэтому настройки падают на старте
    with pytest.raises(ValidationError):
        build_test_settings(CORS_ORIGINS='*', CORS_ALLOW_CREDENTIALS=True)
