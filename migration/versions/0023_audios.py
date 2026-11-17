"""Аудио: таблица audios и связи папок с аудио folder_audios

Revision ID: 0023_audios
Revises: 0022_folder_videos
Create Date: 2026-11-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0023_audios'
down_revision: str | None = '0022_folder_videos'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PG-специфичный ENUM: создаём явно с checkfirst=True, а таблица лишь ссылается.
audio_type = postgresql.ENUM(
    'mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a', 'opus', 'webm', name='audio_type'
)


def upgrade() -> None:
    audio_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'audios',
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
        sa.Column(
            'type',
            postgresql.ENUM(
                'mp3',
                'wav',
                'ogg',
                'aac',
                'flac',
                'm4a',
                'opus',
                'webm',
                name='audio_type',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('object_key'),
    )
    op.create_index(
        'uq_audios_name_active',
        'audios',
        ['name'],
        unique=True,
        postgresql_where=sa.text('deleted_id IS NULL'),
    )

    op.create_table(
        'folder_audios',
        sa.Column('folder_id', sa.UUID(), nullable=False),
        sa.Column('audio_id', sa.UUID(), nullable=False),
        # creator_id — кто привязал аудио к папке (заполняет приложение)
        sa.Column('creator_id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['audio_id'], ['audios.id']),
        sa.PrimaryKeyConstraint('folder_id', 'audio_id'),
    )
    op.create_index('ix_folder_audios_audio_id', 'folder_audios', ['audio_id'])


def downgrade() -> None:
    op.drop_index('ix_folder_audios_audio_id', table_name='folder_audios')
    op.drop_table('folder_audios')
    op.drop_index('uq_audios_name_active', table_name='audios')
    op.drop_table('audios')
    audio_type.drop(op.get_bind(), checkfirst=True)
