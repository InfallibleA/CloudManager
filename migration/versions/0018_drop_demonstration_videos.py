"""Удаление демонстрационных видео

Модуль `demonstration_videos` удалён, поэтому таблица `demonstration_videos`
больше не нужна.

Revision ID: 0018_drop_demonstration_videos
Revises: 0017_drop_services
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0018_drop_demonstration_videos'
down_revision: str | None = '0017_drop_services'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('demonstration_videos')


def downgrade() -> None:
    # Таблица в том виде, в каком её оставили миграции 0009 и 0010
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
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_demonstration_videos_video_id', 'demonstration_videos', ['video_id'])
    op.create_index('ix_demonstration_videos_weight', 'demonstration_videos', ['weight'])
