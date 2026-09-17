"""blocklist name text

Revision ID: 8907e0770476
Revises: 94b53cc4f345
Create Date: 2026-09-18 01:47:23.995095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8907e0770476'
down_revision: Union[str, Sequence[str], None] = '94b53cc4f345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('prohibited_substances', 'name',
               existing_type=sa.VARCHAR(length=512),
               type_=sa.Text(),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('prohibited_substances', 'name',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=512),
               existing_nullable=False)
