from functools import lru_cache
from ipaddress import IPv4Address
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AnyUrl, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.definitions import ENV_FILE


class Settings(BaseSettings):
    DB_SCHEME: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    DB_POOL_SIZE: int
    DB_MAX_OVERFLOW: int

    APP_HOST: IPv4Address | AnyUrl
    APP_PORT: int
    APP_NAME: str
    APP_VERSION: str

    # JWT-авторизация
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = 'HS256'
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # S3-хранилище (Garage)
    S3_ENDPOINT: str = 'garage:3900'
    S3_REGION: str = 'garage'
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str = 'cloudmanager-files'
    S3_SECURE: bool = False
    # Публичный адрес хранилища со стороны браузера: на него подписываются
    # presigned-ссылки на видео. Схема задаёт режим клиента подписи, хост должен
    # совпадать с тем, что открывает браузер (same-origin через nginx-шлюз).
    S3_PUBLIC_ENDPOINT: str = 'http://localhost'

    # Ограничение размера загружаемого файла
    FILE_MAX_SIZE_MB: int = 20

    # Видео: предел размера файла и время жизни presigned-ссылки на воспроизведение
    VIDEO_MAX_SIZE_MB: int = 2048
    VIDEO_PRESIGN_TTL_SECONDS: int = 21600

    # CORS: домены сайта и админки. Списки в env пишутся через запятую,
    # `*` разрешает любой домен (но тогда нельзя использовать cookies)
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ['*']
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOW_METHODS: Annotated[list[str], NoDecode] = ['*']
    CORS_ALLOW_HEADERS: Annotated[list[str], NoDecode] = ['*']

    @field_validator('CORS_ORIGINS', 'CORS_ALLOW_METHODS', 'CORS_ALLOW_HEADERS', mode='before')
    @classmethod
    def split_comma_separated(cls, v: str | list[str]) -> list[str]:
        """Позволяет писать в env список через запятую: `a, b, c`."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        return v

    @model_validator(mode='after')
    def validate_cors(self) -> 'Settings':
        # Браузер отклонит ответ с `*` и cookies сразу — лучше упасть на старте
        if self.CORS_ALLOW_CREDENTIALS and '*' in self.CORS_ORIGINS:
            raise ValueError(
                'CORS_ALLOW_CREDENTIALS=true несовместим с CORS_ORIGINS=*: перечислите домены явно'
            )
        return self

    @field_validator('POSTGRES_PORT')
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v

    @field_validator('VIDEO_PRESIGN_TTL_SECONDS')
    def validate_presign_ttl(cls, v: int) -> int:
        # Подпись AWS SigV4 не поддерживает срок жизни больше 7 суток
        if not 1 <= v <= 604800:
            raise ValueError('VIDEO_PRESIGN_TTL_SECONDS должен быть от 1 до 604800 секунд')
        return v

    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme=self.DB_SCHEME,
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @property
    def s3_public_host(self) -> str:
        """Хост публичного адреса хранилища (без схемы) для клиента подписи."""
        parts = urlsplit(self.S3_PUBLIC_ENDPOINT)
        return parts.netloc or parts.path

    @property
    def s3_public_secure(self) -> bool:
        """Схема публичного адреса: `https` включает TLS у клиента подписи."""
        return urlsplit(self.S3_PUBLIC_ENDPOINT).scheme == 'https'

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra='ignore')


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
