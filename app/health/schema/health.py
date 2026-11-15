from app.core.enums import EHealthStatus
from app.core.schemes.base import CloudManagerBaseModel


class HealthResponseSchema(CloudManagerBaseModel):
    """Состояние сервиса."""

    status: EHealthStatus
    version: str
