from app.core.models.base import Base


class SoftDel(Base):
    """Метка мягкого удаления объекта.

    Обратные связи с User и File не объявлены намеренно: иначе модели зависят от
    порядка импорта (например, CLI работает только с users).
    """

    __tablename__ = 'soft_del'  # noqa
