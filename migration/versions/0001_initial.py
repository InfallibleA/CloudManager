"""Базовые таблицы: soft_del, users, files

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FILE_TYPE = sa.Enum(
    'pdf',
    'doc',
    'docx',
    'xls',
    'xlsx',
    'xlsm',
    'jpeg',
    'jpg',
    'png',
    name='file_type',
)

BASE_COLUMNS = (
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
)


def upgrade() -> None:
    op.create_table(
        'soft_del',
        *BASE_COLUMNS,
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'users',
        *BASE_COLUMNS,
        sa.Column('deleted_id', sa.UUID(), nullable=True),
        sa.Column('login', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('login'),
    )
    op.create_table(
        'files',
        *BASE_COLUMNS,
        sa.Column('deleted_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('minio_id', sa.String(length=255), nullable=False),
        sa.Column('type', FILE_TYPE, nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('minio_id'),
    )


def downgrade() -> None:
    op.drop_table('files')
    op.drop_table('users')
    op.drop_table('soft_del')
    FILE_TYPE.drop(op.get_bind(), checkfirst=True)
