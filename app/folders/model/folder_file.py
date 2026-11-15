from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, Table, Uuid, func

from app.core.models.base import Base

# Связь папок с файлами (многие ко многим).
# creator_id — кто положил файл в папку: заполняется текущим пользователем запроса,
# чтобы по связи было видно автора, а не служебный ROOT_USER.
folder_files = Table(
    'folder_files',
    Base.metadata,
    Column('folder_id', ForeignKey('folders.id', ondelete='CASCADE'), primary_key=True),
    Column('file_id', ForeignKey('files.id'), primary_key=True),
    Column('creator_id', Uuid, nullable=False),
    Column('created_at', TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Index('ix_folder_files_file_id', 'file_id'),
)
