from sqlalchemy.orm import Mapped, mapped_column


class EnumDBMixin:
    name: Mapped[str]
    code: Mapped[str] = mapped_column(unique=True)
