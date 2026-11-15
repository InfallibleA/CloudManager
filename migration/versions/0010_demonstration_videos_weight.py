"""Вес демонстрационных видео

Revision ID: 0010_demonstration_videos_weight
Revises: 0009_demonstration_videos
Create Date: 2026-10-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0010_demonstration_videos_weight'
down_revision: Union[str, None] = '0009_demonstration_videos'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Вес задаёт порядок выдачи, как у products: 0..N-1 без пропусков.
    # Колонка добавляется nullable, чтобы заполнить существующие строки.
    op.add_column('demonstration_videos', sa.Column('weight', sa.Integer(), nullable=True))

    # Существующим записям выдаём веса в порядке создания (id — для устойчивости)
    op.execute('UPDATE demonstration_videos SET weight = 0 WHERE weight IS NULL')
    op.execute(
        """
        UPDATE demonstration_videos AS d
        SET weight = n.rn
        FROM (
            SELECT id, row_number() OVER (ORDER BY created_at, id) - 1 AS rn
            FROM demonstration_videos
        ) AS n
        WHERE d.id = n.id
        """
    )

    op.alter_column('demonstration_videos', 'weight', nullable=False)
    op.create_index('ix_demonstration_videos_weight', 'demonstration_videos', ['weight'])


def downgrade() -> None:
    op.drop_index('ix_demonstration_videos_weight', table_name='demonstration_videos')
    op.drop_column('demonstration_videos', 'weight')
