"""Файлы: новый тип txt

Revision ID: 0012_file_txt_type
Revises: 0011_services
Create Date: 2026-10-15

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0012_file_txt_type'
down_revision: Union[str, None] = '0011_services'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TYPES = ('txt',)
OLD_TYPES = (
    'pdf',
    'doc',
    'docx',
    'xls',
    'xlsx',
    'xlsm',
    'jpeg',
    'jpg',
    'png',
    'gif',
    'webp',
    'avif',
)


def upgrade() -> None:
    # Значения enum добавляются по одному: в PG 12+ это работает внутри транзакции,
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
