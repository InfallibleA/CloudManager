from sqlalchemy import BigInteger, Index, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EVideoType
from app.core.models.base import Base
from app.core.models.soft_del_mixin import SoftDelMixin


class Video(SoftDelMixin, Base):
    __tablename__ = 'videos'
    __table_args__ = (
        # Имя уникально среди неудалённых видео: после мягкого удаления его можно
        # занять снова. Условие `postgresql_where` читает и валидатор репозитория,
        # поэтому дубль отсекается и до INSERT, и на уровне БД.
        Index(
            'uq_videos_name_active',
            'name',
            unique=True,
            postgresql_where=text('deleted_id IS NULL'),
        ),
    )

    # Имя, по которому видео находят в API: уникально среди активных записей
    name: Mapped[str] = mapped_column(String(255))
    # Ключ объекта в S3-хранилище: по нему видео играется и удаляется
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    type: Mapped[EVideoType] = mapped_column(
        SAEnum(EVideoType, name='video_type', values_callable=lambda enum: [e.value for e in enum])
    )
    size: Mapped[int] = mapped_column(BigInteger)
