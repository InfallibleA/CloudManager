from contextlib import asynccontextmanager

import uvicorn
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.config import settings
from app.core.cors import add_cors_middleware
from app.core.di import build_dishka_container
from app.core.exceptions import BaseOrderException
from app.core.exceptions_handlers import order_exception_handler
from app.routers import health_router, router

dishka_container = build_dishka_container()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await dishka_container.close()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# CORS — до роутеров: middleware должен оборачивать все браузерные запросы
add_cors_middleware(app=app, config=settings)

app.add_exception_handler(BaseOrderException, order_exception_handler)

setup_dishka(container=dishka_container, app=app)
app.include_router(router)
# health-пробы без префикса /api — их опрашивает инфраструктура
app.include_router(health_router)

if __name__ == '__main__':
    uvicorn.run(
        'app.main:app', host=str(settings.APP_HOST), port=settings.APP_PORT, workers=1, reload=True
    )
