"""Удаление признака отправки письма у заявок

Почтовые уведомления о заявках удалены, поэтому колонка `leads.mail_sent`
больше не нужна: заявка просто сохраняется в БД.

Revision ID: 0016_drop_lead_mail_sent
Revises: 0015_drop_news_files
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0016_drop_lead_mail_sent'
down_revision: str | None = '0015_drop_news_files'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('leads', 'mail_sent')


def downgrade() -> None:
    op.add_column(
        'leads',
        sa.Column('mail_sent', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
