from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, Table, Uuid, func

from app.core.models.base import Base

# Связь папок с аудио (многие ко многим).
# creator_id — кто положил аудио в папку: заполняется текущим пользователем запроса,
# чтобы по связи было видно автора, а не служебный ROOT_USER.
folder_audios = Table(
    'folder_audios',
    Base.metadata,
    Column('folder_id', ForeignKey('folders.id', ondelete='CASCADE'), primary_key=True),
    Column('audio_id', ForeignKey('audios.id'), primary_key=True),
    Column('creator_id', Uuid, nullable=False),
    Column('created_at', TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Index('ix_folder_audios_audio_id', 'audio_id'),
)
