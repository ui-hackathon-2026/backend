"""supplier location synthetic fields

Revision ID: 5158e2378926
Revises: fc7699b9ea41
Create Date: 2026-09-18 03:28:34.307020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5158e2378926'
down_revision: Union[str, Sequence[str], None] = 'fc7699b9ea41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('suppliers', sa.Column('city', sa.String(length=128), nullable=True))
    op.add_column('suppliers', sa.Column('province', sa.String(length=128), nullable=True))
    op.add_column('suppliers', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('suppliers', sa.Column('lon', sa.Float(), nullable=True))
    op.add_column('suppliers', sa.Column('moq_kg', sa.Float(), nullable=True))
    op.add_column('suppliers', sa.Column('is_synthetic', sa.Boolean(), nullable=True))
    op.add_column('suppliers', sa.Column('external_ref', sa.String(length=64), nullable=True))
    op.execute("UPDATE suppliers SET is_synthetic = false WHERE is_synthetic IS NULL")
    op.alter_column('suppliers', 'is_synthetic', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('suppliers', 'external_ref')
    op.drop_column('suppliers', 'is_synthetic')
    op.drop_column('suppliers', 'moq_kg')
    op.drop_column('suppliers', 'lon')
    op.drop_column('suppliers', 'lat')
    op.drop_column('suppliers', 'province')
    op.drop_column('suppliers', 'city')
