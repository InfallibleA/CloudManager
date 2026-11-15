from enum import Enum
from uuid import UUID

PAGE_LIMIT: int = 100


class BaseEnum(Enum):
    @classmethod
    def values(cls):
        return (c.value for c in cls)


class EUser(BaseEnum):
    FIXTURE_USER = UUID('7541b705-a317-44e4-83ee-2221e5c86ba7')
    ROOT_USER = UUID('99999999-9999-9999-9999-999999999999')
    GUEST_USER = UUID('7d1063d9-14a4-46ac-ae5c-ed4974fb5ef7')
    ADMIN_USER = UUID('d674f194-77da-4fbb-8859-c48d3cda2866')


class EUserRole(BaseEnum):
    """Роль пользователя: администратор управляет контентом, клиент только читает."""

    ADMIN = 'admin'
    CLIENT = 'client'


class EDateTimeFormat(BaseEnum):
    DEFAULT_DATE_FMT: str = '%Y-%m-%d'
    DEFAULT_DATETIME_FMT: str = '%Y-%m-%dT%H:%M:%S'
    DEFAULT_REPORT_DATETIME_FMT: str = '%H:%M:%S %d.%m.%Y'


class EFileType(BaseEnum):
    """Типы файлов, которые принимает API."""

    PDF = 'pdf'
    DOC = 'doc'
    DOCX = 'docx'
    XLS = 'xls'
    XLSX = 'xlsx'
    XLSM = 'xlsm'
    JPEG = 'jpeg'
    JPG = 'jpg'
    PNG = 'png'
    GIF = 'gif'
    WEBP = 'webp'
    AVIF = 'avif'
    TXT = 'txt'


class EVideoType(BaseEnum):
    """Типы видео, которые принимает API."""

    MP4 = 'mp4'
    WEBM = 'webm'


class EHealthStatus(BaseEnum):
    OK = 'ok'
    ERROR = 'error'
