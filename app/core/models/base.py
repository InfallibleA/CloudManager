from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    __abstarct__ = True  # noqa

    type_annotation_map = {
        datetime: TIMESTAMP(timezone=True)
    }

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text('gen_random_uuid()'), sort_order=-1
    )
    creator_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
