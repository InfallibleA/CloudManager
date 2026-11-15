"""Роль пользователя: админ или клиент

Revision ID: 0002_user_role
Revises: 0001_initial
Create Date: 2026-09-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002_user_role'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USER_ROLE = sa.Enum('admin', 'client', name='user_role')


def upgrade() -> None:
    USER_ROLE.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column('role', USER_ROLE, nullable=False, server_default='client'),
    )


def downgrade() -> None:
    op.drop_column('users', 'role')
    USER_ROLE.drop(op.get_bind(), checkfirst=True)
