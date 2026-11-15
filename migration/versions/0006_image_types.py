"""Новые форматы изображений: gif, webp, avif

Revision ID: 0006_image_types
Revises: 0005_leads
Create Date: 2026-10-01

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0006_image_types'
down_revision: Union[str, None] = '0005_leads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TYPES = ('gif', 'webp', 'avif')
OLD_TYPES = ('pdf', 'doc', 'docx', 'xls', 'xlsx', 'xlsm', 'jpeg', 'jpg', 'png')


def upgrade() -> None:
    # Значения enum добавляются по одному. В PG 12+ это работает внутри транзакции,
    # но использовать новое значение можно только после коммита — здесь это и не нужно.
    for file_type in NEW_TYPES:
        op.execute(f"ALTER TYPE file_type ADD VALUE IF NOT EXISTS '{file_type}'")


def downgrade() -> None:
    # Убрать значение enum нельзя, поэтому тип пересоздаётся без новых значений.
    # Если в files уже есть записи с новыми типами, приведение упадёт — это ожидаемо:
    # сначала такие файлы нужно удалить или перенести в старый формат.
    values = ', '.join(f"'{file_type}'" for file_type in OLD_TYPES)
    op.execute('ALTER TYPE file_type RENAME TO file_type_old')
    op.execute(f'CREATE TYPE file_type AS ENUM ({values})')
    op.execute('ALTER TABLE files ALTER COLUMN type TYPE file_type USING type::text::file_type')
    op.execute('DROP TYPE file_type_old')
