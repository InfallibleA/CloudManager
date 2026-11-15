"""Удаление заявок

Модуль `leads` удалён, поэтому таблица `leads` больше не нужна.

Revision ID: 0019_drop_leads
Revises: 0018_drop_demonstration_videos
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0019_drop_leads'
down_revision: str | None = '0018_drop_demonstration_videos'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('leads')


def downgrade() -> None:
    # Таблица в состоянии после 0005 и 0016 (mail_sent уже удалён)
    op.create_table(
        'leads',
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
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('company', sa.String(length=255), server_default='', nullable=False),
        sa.Column('message', sa.Text(), server_default='', nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # Список заявок отдаётся сначала новыми, поэтому дата приёма — под индексом
    op.create_index('ix_leads_created_at', 'leads', ['created_at'])
