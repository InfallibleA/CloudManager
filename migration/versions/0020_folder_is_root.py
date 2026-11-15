"""Корневая папка пользователя

У каждого нового пользователя при регистрации появляется корневая папка
(`is_root = true`), внутри которой он создаёт остальные папки.

Revision ID: 0020_folder_is_root
Revises: 0019_drop_leads
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0020_folder_is_root'
down_revision: str | None = '0019_drop_leads'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'folders',
        sa.Column('is_root', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    # Корневая папка у пользователя одна: частичный уникальный индекс
    op.create_index(
        'uq_folders_root_creator',
        'folders',
        ['creator_id'],
        unique=True,
        postgresql_where=sa.text('is_root AND deleted_id IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_folders_root_creator', table_name='folders')
    op.drop_column('folders', 'is_root')
