"""drop_user_role

Revision ID: e77acdd9bacd
Revises: 3b7b732ac70b
Create Date: 2026-09-17 23:11:13.188010

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e77acdd9bacd'
down_revision: Union[str, Sequence[str], None] = '3b7b732ac70b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('users', 'role')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('role', sa.VARCHAR(length=20), server_default=sa.text("'formulator'::character varying"), autoincrement=False, nullable=False))
