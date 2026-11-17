from typing import Annotated

from fastapi import Query

from app.audios.schema.audios import AudioFilterSchema
from app.core.enums import EAudioType


def get_audio_filters(
    name: Annotated[str | None, Query(max_length=255, description='Поиск по имени аудио')] = None,
    type: Annotated[
        list[EAudioType] | None,
        Query(description='Типы аудио: параметр можно повторить для нескольких типов'),
    ] = None,
) -> AudioFilterSchema:
    """Собирает фильтры списка аудио из query-параметров запроса."""
    return AudioFilterSchema(name=name, types=type or [])
