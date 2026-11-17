from sqlalchemy import BigInteger, Index, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EAudioType
from app.core.models.base import Base
from app.core.models.soft_del_mixin import SoftDelMixin


class Audio(SoftDelMixin, Base):
    __tablename__ = 'audios'
    __table_args__ = (
        # Имя уникально среди неудалённых аудио: после мягкого удаления его можно
        # занять снова. Условие `postgresql_where` читает и валидатор репозитория,
        # поэтому дубль отсекается и до INSERT/UPDATE, и на уровне БД.
        Index(
            'uq_audios_name_active',
            'name',
            unique=True,
            postgresql_where=text('deleted_id IS NULL'),
        ),
    )

    # Имя, по которому аудио находят в API: уникально среди активных записей
    name: Mapped[str] = mapped_column(String(255))
    # Ключ объекта в S3-хранилище: по нему аудио воспроизводится и удаляется
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    type: Mapped[EAudioType] = mapped_column(
        SAEnum(EAudioType, name='audio_type', values_callable=lambda enum: [e.value for e in enum])
    )
    size: Mapped[int] = mapped_column(BigInteger)
