"""Удаление связи новостей с файлами

У новости остаётся только главное изображение (`media_id`), поэтому таблица
связей `news_files` больше не нужна.

Revision ID: 0015_drop_news_files
Revises: 0014_rename_products_to_news
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0015_drop_news_files'
down_revision: str | None = '0014_rename_products_to_news'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('news_files')


def downgrade() -> None:
    op.create_table(
        'news_files',
        sa.Column('news_id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id']),
        sa.PrimaryKeyConstraint('news_id', 'file_id'),
    )
    op.create_index('ix_news_files_file_id', 'news_files', ['file_id'])
