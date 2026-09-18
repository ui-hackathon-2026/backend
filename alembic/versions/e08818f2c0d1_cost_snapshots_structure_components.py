"""cost snapshots structure components

Revision ID: e08818f2c0d1
Revises: 5158e2378926
Create Date: 2026-09-18 06:56:47.892043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e08818f2c0d1'
down_revision: Union[str, Sequence[str], None] = '5158e2378926'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('ingredient_structure_components',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('ingredient_inci', sa.String(length=255), nullable=False),
    sa.Column('representation_type', sa.String(length=32), nullable=False),
    sa.Column('smiles', sa.String(length=1024), nullable=True),
    sa.Column('marker_name', sa.String(length=255), nullable=True),
    sa.Column('caveat_note', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingredient_structure_components_ingredient_inci'), 'ingredient_structure_components', ['ingredient_inci'], unique=False)
    op.add_column('formula_ingredients', sa.Column('supplier_offer_id', sa.Integer(), nullable=True))
    op.add_column('formula_ingredients', sa.Column('cost_idr_per_kg', sa.Float(), nullable=True))
    op.add_column('formula_ingredients', sa.Column('tkdn_pct', sa.Float(), nullable=True))
    op.add_column('formula_ingredients', sa.Column('cost_source', sa.String(length=32), nullable=True))
    op.execute("UPDATE formula_ingredients SET cost_source = 'unknown' WHERE cost_source IS NULL")
    op.alter_column('formula_ingredients', 'cost_source', nullable=False)
    op.add_column('ingredients', sa.Column('structure_representation_type', sa.String(length=32), nullable=True))
    op.execute("UPDATE ingredients SET structure_representation_type = 'unresolved' WHERE structure_representation_type IS NULL")
    op.alter_column('ingredients', 'structure_representation_type', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ingredients', 'structure_representation_type')
    op.drop_column('formula_ingredients', 'cost_source')
    op.drop_column('formula_ingredients', 'tkdn_pct')
    op.drop_column('formula_ingredients', 'cost_idr_per_kg')
    op.drop_column('formula_ingredients', 'supplier_offer_id')
    op.drop_index(op.f('ix_ingredient_structure_components_ingredient_inci'), table_name='ingredient_structure_components')
    op.drop_table('ingredient_structure_components')
