"""Главное изображение продукта: products.media_id

Revision ID: 0007_product_media
Revises: 0006_image_types
Create Date: 2026-10-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007_product_media'
down_revision: Union[str, None] = '0006_image_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # media_id — ссылка на файл-изображение из модуля files, может отсутствовать
    op.add_column('products', sa.Column('media_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_products_media_id_files', 'products', 'files', ['media_id'], ['id']
    )
    op.create_index('ix_products_media_id', 'products', ['media_id'])


def downgrade() -> None:
    op.drop_index('ix_products_media_id', table_name='products')
    op.drop_constraint('fk_products_media_id_files', 'products', type_='foreignkey')
    op.drop_column('products', 'media_id')
