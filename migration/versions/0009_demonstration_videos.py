"""Демонстрационные видео: таблица demonstration_videos

Revision ID: 0009_demonstration_videos
Revises: 0008_videos
Create Date: 2026-10-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0009_demonstration_videos'
down_revision: Union[str, None] = '0008_videos'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'demonstration_videos',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('creator_id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('deleted_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('video_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # Ссылка на видео: по ней ищут зависимости и проверяют существование
    op.create_index('ix_demonstration_videos_video_id', 'demonstration_videos', ['video_id'])


def downgrade() -> None:
    op.drop_index('ix_demonstration_videos_video_id', table_name='demonstration_videos')
    op.drop_table('demonstration_videos')
