from app.core.enums import EVideoType

# MIME-типы, с которыми видео хранится в S3-хранилище и отдаётся браузеру
VIDEO_TYPE_CONTENT_TYPES: dict[EVideoType, str] = {
    EVideoType.MP4: 'video/mp4',
    EVideoType.WEBM: 'video/webm',
}

# Разрешённые расширения видео (совпадают со значениями EVideoType)
VIDEO_TYPES: frozenset[str] = frozenset(video_type.value for video_type in EVideoType)

# Список для подсказок в OpenAPI и текстов ошибок — чтобы не расходился с enum
VIDEO_TYPES_HINT: str = ', '.join(sorted(VIDEO_TYPES))


def video_type_by_extension(extension: str) -> EVideoType | None:
    """Определяет тип видео по расширению. Точка и регистр значения не имеют."""
    try:
        return EVideoType(extension.lstrip('.').lower())
    except ValueError:
        return None


def content_type_for(video_type: EVideoType) -> str:
    """Возвращает MIME-тип видео."""
    return VIDEO_TYPE_CONTENT_TYPES[video_type]
