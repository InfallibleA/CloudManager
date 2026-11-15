from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models.base import Base
from app.core.models.soft_del_mixin import SoftDelMixin


class News(SoftDelMixin, Base):
    __tablename__ = 'news'

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, server_default='')
    # Вес записи задаёт порядок выдачи: уникален и начинается с 0
    weight: Mapped[int] = mapped_column(Integer, index=True)
    # Главное изображение новости: ссылка на файл-картинку из модуля files
    media_id: Mapped[UUID | None] = mapped_column(ForeignKey('files.id'), index=True)
