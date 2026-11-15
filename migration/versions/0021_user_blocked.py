"""Блокировка пользователей

Заблокированный пользователь не может войти и пользоваться API.

Revision ID: 0021_user_blocked
Revises: 0020_folder_is_root
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0021_user_blocked'
down_revision: str | None = '0020_folder_is_root'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_blocked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_blocked')
