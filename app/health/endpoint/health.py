from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.config import Settings
from app.core.engines.database import Transaction
from app.core.enums import EHealthStatus
from app.health.schema.health import HealthResponseSchema

router = APIRouter(prefix='/health', tags=['health'])


@router.get('', summary='Liveness-проба сервиса')
@inject
async def health(config: FromDishka[Settings]) -> HealthResponseSchema:
    return HealthResponseSchema(status=EHealthStatus.OK, version=config.APP_VERSION)


@router.get('/ready', summary='Readiness-проба: сервис и подключение к БД')
@inject
async def ready(
    response: Response,
    transaction: FromDishka[Transaction],
    config: FromDishka[Settings],
) -> HealthResponseSchema:
    try:
        await transaction.execute(text('SELECT 1'))
    except Exception:  # noqa: BLE001 — любая ошибка БД означает неготовность
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponseSchema(status=EHealthStatus.ERROR, version=config.APP_VERSION)

    return HealthResponseSchema(status=EHealthStatus.OK, version=config.APP_VERSION)
