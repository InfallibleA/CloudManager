from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

# Эти заголовки браузер отдаёт фронтенду только если их явно разрешить:
# без `Content-Disposition` не видно имя файла при скачивании через fetch/XHR
EXPOSED_HEADERS = ['Content-Disposition', 'Content-Length']


def add_cors_middleware(app: FastAPI, *, config: Settings) -> None:
    """Разрешает браузерные запросы с сайта и админки.

    Домены задаются в `CORS_ORIGINS` через запятую, `*` разрешает любой домен.
    Авторизация в проекте — Bearer-токен, поэтому cookies по умолчанию выключены
    (`CORS_ALLOW_CREDENTIALS=false`).
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=config.CORS_ALLOW_CREDENTIALS,
        allow_methods=config.CORS_ALLOW_METHODS,
        allow_headers=config.CORS_ALLOW_HEADERS,
        expose_headers=EXPOSED_HEADERS,
        max_age=600,
    )
