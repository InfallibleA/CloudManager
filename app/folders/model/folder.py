from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models.base import Base
from app.core.models.soft_del_mixin import SoftDelMixin


class Folder(SoftDelMixin, Base):
    """Папка пользователя: может лежать внутри корневой или любой другой папки."""

    __tablename__ = 'folders'
    __table_args__ = (
        # Корневая папка у пользователя одна: частичный уникальный индекс
        # не даст создать вторую (удалённые записи не мешают).
        Index(
            'uq_folders_root_creator',
            'creator_id',
            unique=True,
            postgresql_where=text('is_root AND deleted_id IS NULL'),
        ),
    )

    # Имя, под которым папка видна пользователю
    name: Mapped[str] = mapped_column(String(255))
    # Родительская папка: NULL — верхний уровень. Вложение не ограничено по глубине
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey('folders.id'), index=True)
    # Корневая папка создаётся при регистрации: от неё строится всё дерево пользователя
    is_root: Mapped[bool] = mapped_column(Boolean, server_default=text('false'), default=False)
