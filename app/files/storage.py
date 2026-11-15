import asyncio
from datetime import timedelta
from io import BytesIO
from typing import BinaryIO

from minio import Minio

from app.config import Settings
from app.core.exceptions import InternalServerException


class FileStorage:
    """Обёртка над S3-хранилищем Garage.

    Используется синхронный S3-клиент (пакет `minio`): он блокирует поток,
    поэтому все обращения уходят в отдельный поток.
    """

    def __init__(self, *, config: Settings):
        self._bucket = config.S3_BUCKET
        self._client = Minio(
            endpoint=config.S3_ENDPOINT,
            access_key=config.S3_ACCESS_KEY,
            secret_key=config.S3_SECRET_KEY,
            secure=config.S3_SECURE,
            region=config.S3_REGION,
        )
        # Отдельный клиент для подписи: presigned-ссылка подписана под Host, который
        # откроет браузер, поэтому её нельзя строить по внутреннему `garage:3900`.
        # Подпись считается локально, сети этот клиент не касается.
        self._presign_client = Minio(
            endpoint=config.s3_public_host,
            access_key=config.S3_ACCESS_KEY,
            secret_key=config.S3_SECRET_KEY,
            secure=config.s3_public_secure,
            region=config.S3_REGION,
        )
        self._bucket_checked = False

    async def check_bucket(self) -> None:
        """Проверяет, что бакет существует.

        Бакет создаётся при инициализации хранилища (см. README): у ключа
        приложения нет права на создание бакетов.
        """
        if self._bucket_checked:
            return

        exists = await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        if not exists:
            raise InternalServerException(detail=f'Бакет {self._bucket} не найден в S3-хранилище.')
        self._bucket_checked = True

    async def upload(self, *, object_id: str, data: bytes, content_type: str) -> None:
        """Загружает объект в хранилище."""
        await self.check_bucket()
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            object_id,
            BytesIO(data),
            len(data),
            content_type=content_type,
        )

    async def upload_stream(
        self, *, object_id: str, stream: BinaryIO, length: int, content_type: str
    ) -> None:
        """Загружает объект потоком, не читая его целиком в память.

        Garage сам шлёт файл частями (`put_object` с известной длиной), поэтому
        видео на гигабайты не занимает оперативную память целиком.
        """
        await self.check_bucket()
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            object_id,
            stream,
            length,
            content_type=content_type,
        )

    async def download(self, *, object_id: str) -> bytes:
        """Возвращает содержимое объекта."""

        def _read() -> bytes:
            response = self._client.get_object(self._bucket, object_id)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_read)

    async def remove(self, *, object_id: str) -> None:
        """Удаляет объект из хранилища."""
        await asyncio.to_thread(self._client.remove_object, self._bucket, object_id)

    def presign_get(self, *, object_id: str, expires_seconds: int) -> str:
        """Возвращает presigned-ссылку на чтение объекта.

        Подпись привязана к хосту и пути, поэтому ссылку строит публичный клиент:
        браузер обратится к тому же хосту, что и S3 (через nginx).
        """
        return self._presign_client.presigned_get_object(
            self._bucket, object_id, expires=timedelta(seconds=expires_seconds)
        )
