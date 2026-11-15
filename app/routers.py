from fastapi import APIRouter

from app.auth.endpoint.auth import router as auth_router
from app.files.endpoint.files import router as files_router
from app.folders.endpoint.folders import router as folders_router
from app.health.endpoint.health import router as health_router
from app.news.endpoint.news import router as news_router
from app.videos.endpoint.videos import router as videos_router

# API приложения под общим префиксом /api
router = APIRouter(prefix='/api')
router.include_router(auth_router)
router.include_router(files_router)
router.include_router(folders_router)
router.include_router(news_router)
router.include_router(videos_router)

__all__ = ['health_router', 'router']
