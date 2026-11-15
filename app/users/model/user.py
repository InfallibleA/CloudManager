from sqlalchemy import Boolean, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EUserRole
from app.core.models.base import Base
from app.core.models.soft_del_mixin import SoftDelMixin


class User(SoftDelMixin, Base):
    __tablename__ = 'users'

    login: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[EUserRole] = mapped_column(
        SAEnum(EUserRole, name='user_role', values_callable=lambda enum: [e.value for e in enum]),
        server_default=EUserRole.CLIENT.value,
    )
    # Заблокированный пользователь не может войти и пользоваться API
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, server_default=text('false'), default=False
    )
