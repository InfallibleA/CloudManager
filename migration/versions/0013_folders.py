"""Папки и связи папок с файлами

Revision ID: 0013_folders
Revises: 0012_file_txt_type
Create Date: 2026-10-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0013_folders'
down_revision: Union[str, None] = '0012_file_txt_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'folders',
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
        # NULL — папка верхнего уровня; ссылка на себя же задаёт вложенность
        sa.Column('parent_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_id'], ['soft_del.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['folders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # Папки личные: выборки идут по владельцу, содержимое — по родителю
    op.create_index('ix_folders_creator_id', 'folders', ['creator_id'])
    op.create_index('ix_folders_parent_id', 'folders', ['parent_id'])

    op.create_table(
        'folder_files',
        sa.Column('folder_id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        # creator_id — кто привязал файл к папке (заполняет приложение)
        sa.Column('creator_id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id']),
        sa.PrimaryKeyConstraint('folder_id', 'file_id'),
    )
    op.create_index('ix_folder_files_file_id', 'folder_files', ['file_id'])


def downgrade() -> None:
    op.drop_index('ix_folder_files_file_id', table_name='folder_files')
    op.drop_table('folder_files')
    op.drop_index('ix_folders_parent_id', table_name='folders')
    op.drop_index('ix_folders_creator_id', table_name='folders')
    op.drop_table('folders')
