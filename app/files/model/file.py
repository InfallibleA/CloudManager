from sqlalchemy import BigInteger, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EFileType
from app.core.models.base import Base
from app.core.models.soft_del_mixin import SoftDelMixin


class File(SoftDelMixin, Base):
    __tablename__ = 'files'

    # Имя файла, под которым он виден пользователю
    name: Mapped[str] = mapped_column(String(255))
    # Ключ объекта в S3-хранилище: по нему файл скачивается и удаляется
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    type: Mapped[EFileType] = mapped_column(
        SAEnum(EFileType, name='file_type', values_callable=lambda enum: [e.value for e in enum])
    )
    size: Mapped[int] = mapped_column(BigInteger)
