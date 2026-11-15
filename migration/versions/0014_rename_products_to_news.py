"""Переименование products → news

Переименовывает таблицы продуктов в новости: `products` → `news`,
`product_files` → `news_files` (с колонкой `product_id` → `news_id`),
а также индексы и констрейнты, в именах которых осталось старое название.
Данные не теряются: операция только переименовывает объекты БД.

Revision ID: 0014_rename_products_to_news
Revises: 0013_folders
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0014_rename_products_to_news'
down_revision: str | None = '0013_folders'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Таблицы: основная, затем связи (FK переезжает вместе с таблицей)
    op.execute('ALTER TABLE products RENAME TO news')
    op.execute('ALTER TABLE product_files RENAME TO news_files')
    op.execute('ALTER TABLE news_files RENAME COLUMN product_id TO news_id')

    # Индексы создавались миграциями 0004 и 0007 под старые имена
    op.execute('ALTER INDEX ix_products_weight RENAME TO ix_news_weight')
    op.execute('ALTER INDEX ix_products_media_id RENAME TO ix_news_media_id')
    op.execute('ALTER INDEX ix_product_files_file_id RENAME TO ix_news_files_file_id')

    # PK и FK: у PK-констрейнта индекс переименовывается вместе с констрейнтом
    op.execute('ALTER TABLE news RENAME CONSTRAINT products_pkey TO news_pkey')
    op.execute(
        'ALTER TABLE news RENAME CONSTRAINT products_deleted_id_fkey TO news_deleted_id_fkey'
    )
    op.execute(
        'ALTER TABLE news RENAME CONSTRAINT fk_products_media_id_files TO fk_news_media_id_files'
    )
    op.execute('ALTER TABLE news_files RENAME CONSTRAINT product_files_pkey TO news_files_pkey')
    op.execute(
        'ALTER TABLE news_files '
        'RENAME CONSTRAINT product_files_file_id_fkey TO news_files_file_id_fkey'
    )
    op.execute(
        'ALTER TABLE news_files '
        'RENAME CONSTRAINT product_files_product_id_fkey TO news_files_news_id_fkey'
    )


def downgrade() -> None:
    op.execute(
        'ALTER TABLE news_files '
        'RENAME CONSTRAINT news_files_news_id_fkey TO product_files_product_id_fkey'
    )
    op.execute(
        'ALTER TABLE news_files '
        'RENAME CONSTRAINT news_files_file_id_fkey TO product_files_file_id_fkey'
    )
    op.execute('ALTER TABLE news_files RENAME CONSTRAINT news_files_pkey TO product_files_pkey')
    op.execute(
        'ALTER TABLE news RENAME CONSTRAINT fk_news_media_id_files TO fk_products_media_id_files'
    )
    op.execute(
        'ALTER TABLE news RENAME CONSTRAINT news_deleted_id_fkey TO products_deleted_id_fkey'
    )
    op.execute('ALTER TABLE news RENAME CONSTRAINT news_pkey TO products_pkey')

    op.execute('ALTER INDEX ix_news_files_file_id RENAME TO ix_product_files_file_id')
    op.execute('ALTER INDEX ix_news_media_id RENAME TO ix_products_media_id')
    op.execute('ALTER INDEX ix_news_weight RENAME TO ix_products_weight')

    op.execute('ALTER TABLE news_files RENAME COLUMN news_id TO product_id')
    op.execute('ALTER TABLE news_files RENAME TO product_files')
    op.execute('ALTER TABLE news RENAME TO products')
