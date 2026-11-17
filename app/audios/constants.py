from app.core.enums import EAudioType

# MIME-типы, с которыми аудио хранится в S3-хранилище и отдаётся браузеру
AUDIO_TYPE_CONTENT_TYPES: dict[EAudioType, str] = {
    EAudioType.MP3: 'audio/mpeg',
    EAudioType.WAV: 'audio/wav',
    EAudioType.OGG: 'audio/ogg',
    EAudioType.AAC: 'audio/aac',
    EAudioType.FLAC: 'audio/flac',
    EAudioType.M4A: 'audio/mp4',
    EAudioType.OPUS: 'audio/opus',
    EAudioType.WEBM: 'audio/webm',
}

# Разрешённые расширения аудио (совпадают со значениями EAudioType)
AUDIO_TYPES: frozenset[str] = frozenset(audio_type.value for audio_type in EAudioType)

# Список для подсказок в OpenAPI и текстов ошибок — чтобы не расходился с enum
AUDIO_TYPES_HINT: str = ', '.join(sorted(AUDIO_TYPES))


def audio_type_by_extension(extension: str) -> EAudioType | None:
    """Определяет тип аудио по расширению. Точка и регистр значения не имеют."""
    try:
        return EAudioType(extension.lstrip('.').lower())
    except ValueError:
        return None


def content_type_for(audio_type: EAudioType) -> str:
    """Возвращает MIME-тип аудио."""
    return AUDIO_TYPE_CONTENT_TYPES[audio_type]
