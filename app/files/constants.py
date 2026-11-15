from app.core.enums import EFileType

# MIME-типы, с которыми файл хранится в S3-хранилище и отдаётся клиенту
FILE_TYPE_CONTENT_TYPES: dict[EFileType, str] = {
    EFileType.PDF: 'application/pdf',
    EFileType.DOC: 'application/msword',
    EFileType.DOCX: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    EFileType.XLS: 'application/vnd.ms-excel',
    EFileType.XLSX: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    EFileType.XLSM: 'application/vnd.ms-excel.sheet.macroEnabled.12',
    EFileType.JPEG: 'image/jpeg',
    EFileType.JPG: 'image/jpeg',
    EFileType.PNG: 'image/png',
    EFileType.GIF: 'image/gif',
    EFileType.WEBP: 'image/webp',
    EFileType.AVIF: 'image/avif',
    EFileType.TXT: 'text/plain',
}

# Разрешённые расширения файлов (совпадают со значениями EFileType)
FILE_TYPES: frozenset[str] = frozenset(file_type.value for file_type in EFileType)

# Типы-изображения: их можно отдавать браузеру инлайном для показа в <img>
IMAGE_TYPES: frozenset[EFileType] = frozenset(
    {
        EFileType.JPEG,
        EFileType.JPG,
        EFileType.PNG,
        EFileType.GIF,
        EFileType.WEBP,
        EFileType.AVIF,
    }
)

# Списки для подсказок в OpenAPI и текстов ошибок — чтобы они не расходились с enum
FILE_TYPES_HINT: str = ', '.join(sorted(FILE_TYPES))
IMAGE_TYPES_HINT: str = ', '.join(sorted(image_type.value for image_type in IMAGE_TYPES))


def file_type_by_extension(extension: str) -> EFileType | None:
    """Определяет тип файла по расширению. Точка и регистр значения не имеют."""
    try:
        return EFileType(extension.lstrip('.').lower())
    except ValueError:
        return None


def content_type_for(file_type: EFileType) -> str:
    """Возвращает MIME-тип файла."""
    return FILE_TYPE_CONTENT_TYPES[file_type]


def is_image_type(file_type: EFileType) -> bool:
    """Проверяет, что тип файла — изображение (можно показать в <img>)."""
    return file_type in IMAGE_TYPES
