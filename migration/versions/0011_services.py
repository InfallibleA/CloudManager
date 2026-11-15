"""Услуги: таблица services

Revision ID: 0011_services
Revises: 0010_demonstration_videos_weight
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0011_services'
down_revision: Union[str, None] = '0010_demonstration_videos_weight'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index('ix_services_media_id', table_name='services')
    op.drop_index('ix_services_weight', table_name='services')
    op.drop_table('services')
