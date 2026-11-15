from typing import Annotated
from uuid import UUID

from fastapi import Query

from app.core.enums import EFileType
from app.files.schema.files import FileFilterSchema


def get_file_filters(
    name: Annotated[str | None, Query(max_length=255, description='Поиск по имени файла')] = None,
    type: Annotated[
        list[EFileType] | None,
        Query(description='Типы файлов: параметр можно повторить для нескольких типов'),
    ] = None,
    creator_id: Annotated[
        UUID | None, Query(description='Файлы конкретного пользователя (id аккаунта)')
    ] = None,
) -> FileFilterSchema:
    """Собирает фильтры списка файлов из query-параметров запроса."""
    return FileFilterSchema(name=name, types=type or [], creator_id=creator_id)
