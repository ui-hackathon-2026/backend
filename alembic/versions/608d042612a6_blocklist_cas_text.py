"""blocklist cas text

Revision ID: 608d042612a6
Revises: 8907e0770476
Create Date: 2026-09-18 01:48:29.912101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '608d042612a6'
down_revision: Union[str, Sequence[str], None] = '8907e0770476'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('prohibited_substances', 'cas_number',
               existing_type=sa.VARCHAR(length=64),
               type_=sa.Text(),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('prohibited_substances', 'cas_number',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=64),
               existing_nullable=True)
