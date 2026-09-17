"""ingredient catalog enrichment columns

Revision ID: 383a10a7e482
Revises: 5ee5037ac5ce
Create Date: 2026-09-17 21:33:37.676448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '383a10a7e482'
down_revision: Union[str, Sequence[str], None] = '5ee5037ac5ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ingredients', sa.Column('cas_number', sa.String(length=64), nullable=True))
    op.add_column('ingredients', sa.Column('default_weight_pct', sa.Float(), nullable=True))
    op.add_column('ingredients', sa.Column('min_recommended_pct', sa.Float(), nullable=True))
    op.add_column('ingredients', sa.Column('max_recommended_pct', sa.Float(), nullable=True))
    op.add_column('ingredients', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ingredients', 'description')
    op.drop_column('ingredients', 'max_recommended_pct')
    op.drop_column('ingredients', 'min_recommended_pct')
    op.drop_column('ingredients', 'default_weight_pct')
    op.drop_column('ingredients', 'cas_number')
