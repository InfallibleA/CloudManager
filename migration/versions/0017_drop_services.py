"""Удаление услуг

Модуль `services` удалён, поэтому таблица `services` больше не нужна.

Revision ID: 0017_drop_services
Revises: 0016_drop_lead_mail_sent
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0017_drop_services'
down_revision: str | None = '0016_drop_lead_mail_sent'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('services')


def downgrade() -> None:
    op.create_table(
        'services',
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
        # description и detailed_description необязательны: NULL, если текст не задан
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('detailed_description', sa.Text(), nullable=True),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.ForeignKeyConstraint(['media_id'], ['files.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_services_weight', 'services', ['weight'])
    op.create_index('ix_services_media_id', 'services', ['media_id'])
