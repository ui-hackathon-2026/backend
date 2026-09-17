"""ingredient origin column

Revision ID: 6ad16fc1b728
Revises: ce2e493cbec7
Create Date: 2026-09-17 22:10:38.495843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6ad16fc1b728'
down_revision: Union[str, Sequence[str], None] = 'ce2e493cbec7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ingredients', sa.Column('origin', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ingredients', 'origin')
