"""competitor products

Revision ID: fc7699b9ea41
Revises: d14f817704d1
Create Date: 2026-09-18 02:41:51.644791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fc7699b9ea41'
down_revision: Union[str, Sequence[str], None] = 'd14f817704d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('competitor_products',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('brand', sa.String(length=128), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=512), nullable=False),
    sa.Column('url', sa.String(length=1024), nullable=False),
    sa.Column('inci_list', sa.JSON(), nullable=False),
    sa.Column('ingredient_count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_competitor_products_brand'), 'competitor_products', ['brand'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_competitor_products_brand'), table_name='competitor_products')
    op.drop_table('competitor_products')
