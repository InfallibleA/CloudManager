"""Переименование files.minio_id в object_key

Revision ID: 0003_object_key
Revises: 0002_user_role
Create Date: 2026-09-29

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_object_key'
down_revision: Union[str, None] = '0002_user_role'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('files', 'minio_id', new_column_name='object_key')
    # имя уникального ограничения, созданного в 0001_initial
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'files_minio_id_key') THEN
                ALTER TABLE files RENAME CONSTRAINT files_minio_id_key TO files_object_key_key;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'files_object_key_key') THEN
                ALTER TABLE files RENAME CONSTRAINT files_object_key_key TO files_minio_id_key;
            END IF;
        END $$;
        """
    )
    op.alter_column('files', 'object_key', new_column_name='minio_id')
