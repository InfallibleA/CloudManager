from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

# импорт нужен, чтобы SQLAlchemy нашёл SoftDel при конфигурации мапперов
from app.core.models.soft_del import SoftDel  # noqa: F401


class SoftDelMixin:
    deleted_id: Mapped[UUID | None] = mapped_column(ForeignKey('soft_del.id'))

    @declared_attr
    def soft_del(self):
        return relationship('SoftDel')
