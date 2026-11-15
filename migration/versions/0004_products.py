"""Таблицы продуктов и связи продуктов с файлами

Revision ID: 0004_products
Revises: 0003_object_key
Create Date: 2026-09-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004_products'
down_revision: Union[str, None] = '0003_object_key'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'products',
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
        sa.Column('description', sa.Text(), server_default='', nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_products_weight', 'products', ['weight'])

    op.create_table(
        'product_files',
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id']),
        sa.PrimaryKeyConstraint('product_id', 'file_id'),
    )
    op.create_index('ix_product_files_file_id', 'product_files', ['file_id'])


def downgrade() -> None:
    op.drop_index('ix_product_files_file_id', table_name='product_files')
    op.drop_table('product_files')
    op.drop_index('ix_products_weight', table_name='products')
    op.drop_table('products')
