from typing import Annotated
from uuid import UUID

from fastapi import Query

from app.folders.schema.folders import FolderFilterSchema


def get_folder_filters(
    name: Annotated[str | None, Query(max_length=255, description='Поиск по названию')] = None,
    parent_id: Annotated[UUID | None, Query(description='Содержимое папки')] = None,
    root_only: Annotated[
        bool, Query(description='Только папки верхнего уровня (игнорируется с parent_id)')
    ] = False,
    creator_id: Annotated[
        UUID | None,
        Query(description='Папки конкретного пользователя: только для админа'),
    ] = None,
) -> FolderFilterSchema:
    """Собирает фильтры списка папок из query-параметров запроса."""
    return FolderFilterSchema(
        name=name, parent_id=parent_id, root_only=root_only, creator_id=creator_id
    )
