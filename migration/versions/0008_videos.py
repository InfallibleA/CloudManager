"""Видео: таблица videos и уникальное имя

Revision ID: 0008_videos
Revises: 0007_product_media
Create Date: 2026-10-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0008_videos'
down_revision: Union[str, None] = '0007_product_media'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PG-специфичный ENUM: у generic sa.Enum нет `create_type`, поэтому op.create_table
# создавал бы тип повторно после явного video_type.create() и падал с already exists.
video_type = postgresql.ENUM('mp4', 'webm', name='video_type')


def upgrade() -> None:
    video_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'videos',
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
        sa.Column('object_key', sa.String(length=255), nullable=False),
        # create_type=False: тип уже создан выше, таблица лишь ссылается на него
        sa.Column(
            'type',
            postgresql.ENUM('mp4', 'webm', name='video_type', create_type=False),
            nullable=False,
        ),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('object_key'),
    )
    # Имя уникально только среди неудалённых видео: удалённую запись не учитываем
    op.create_index(
        'uq_videos_name_active',
        'videos',
        ['name'],
        unique=True,
        postgresql_where=sa.text('deleted_id IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_videos_name_active', table_name='videos')
    op.drop_table('videos')
    video_type.drop(op.get_bind(), checkfirst=True)
