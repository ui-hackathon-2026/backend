"""jobs batch suppliers

Revision ID: 5ee5037ac5ce
Revises: bd6f072058e9
Create Date: 2026-09-17 21:16:09.244614

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5ee5037ac5ce'
down_revision: Union[str, Sequence[str], None] = 'bd6f072058e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('optimization_jobs',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('suppliers',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('ingredient_inci', sa.String(length=255), nullable=True),
    sa.Column('grade', sa.String(length=128), nullable=True),
    sa.Column('halal_certified', sa.Boolean(), nullable=False),
    sa.Column('lead_time_days', sa.Integer(), nullable=True),
    sa.Column('price_per_kg_idr', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('batch_records',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('formula_id', sa.String(length=64), nullable=False),
    sa.Column('batch_size_g', sa.Float(), nullable=False),
    sa.Column('operator_name', sa.String(length=255), nullable=True),
    sa.Column('scaled_ingredients', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['formula_id'], ['formulas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_batch_records_formula_id'), 'batch_records', ['formula_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_batch_records_formula_id'), table_name='batch_records')
    op.drop_table('batch_records')
    op.drop_table('suppliers')
    op.drop_table('optimization_jobs')
