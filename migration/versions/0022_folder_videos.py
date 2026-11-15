"""Связи папок с видео

Видео можно положить в папку наравне с файлами: связь многие ко многим,
папка отдаёт их вместе с файлами в `GET /api/folders/{id}`.

Revision ID: 0022_folder_videos
Revises: 0021_user_blocked
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0022_folder_videos'
down_revision: str | None = '0021_user_blocked'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'folder_videos',
        sa.Column('folder_id', sa.UUID(), nullable=False),
        sa.Column('video_id', sa.UUID(), nullable=False),
        # creator_id — кто привязал видео к папке (заполняет приложение)
        sa.Column('creator_id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
        sa.PrimaryKeyConstraint('folder_id', 'video_id'),
    )
    op.create_index('ix_folder_videos_video_id', 'folder_videos', ['video_id'])


def downgrade() -> None:
    op.drop_index('ix_folder_videos_video_id', table_name='folder_videos')
    op.drop_table('folder_videos')
