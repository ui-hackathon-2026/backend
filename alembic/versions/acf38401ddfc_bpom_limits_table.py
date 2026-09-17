"""bpom limits table

Revision ID: acf38401ddfc
Revises: 6836ab14a350
Create Date: 2026-09-17 20:26:04.509248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'acf38401ddfc'
down_revision: Union[str, Sequence[str], None] = '6836ab14a350'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('bpom_limits',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('inci', sa.String(length=255), nullable=False),
    sa.Column('max_pct', sa.Float(), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('regulation_ref', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bpom_limits_inci'), 'bpom_limits', ['inci'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bpom_limits_inci'), table_name='bpom_limits')
    op.drop_table('bpom_limits')
