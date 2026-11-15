from typing import Annotated

from fastapi import Query

from app.core.enums import EVideoType
from app.videos.schema.videos import VideoFilterSchema


def get_video_filters(
    name: Annotated[str | None, Query(max_length=255, description='Поиск по имени видео')] = None,
    type: Annotated[
        list[EVideoType] | None,
        Query(description='Типы видео: параметр можно повторить для нескольких типов'),
    ] = None,
) -> VideoFilterSchema:
    """Собирает фильтры списка видео из query-параметров запроса."""
    return VideoFilterSchema(name=name, types=type or [])
