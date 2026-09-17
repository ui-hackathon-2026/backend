"""formula tables

Revision ID: 6836ab14a350
Revises: ab0fea9117a4
Create Date: 2026-09-17 19:39:28.252659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6836ab14a350'
down_revision: Union[str, Sequence[str], None] = 'ab0fea9117a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('formulas',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=128), nullable=True),
    sa.Column('batch_size_g', sa.Float(), nullable=False),
    sa.Column('notes', sa.String(length=1024), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('formula_ingredients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('formula_id', sa.String(length=64), nullable=False),
    sa.Column('phase', sa.String(length=1), nullable=False),
    sa.Column('inci', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('smiles', sa.String(length=1024), nullable=True),
    sa.Column('weight_pct', sa.Float(), nullable=False),
    sa.Column('is_locked', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['formula_id'], ['formulas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_formula_ingredients_formula_id'), 'formula_ingredients', ['formula_id'], unique=False)
    op.create_table('formula_versions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('formula_id', sa.String(length=64), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['formula_id'], ['formulas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_formula_versions_formula_id'), 'formula_versions', ['formula_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_formula_versions_formula_id'), table_name='formula_versions')
    op.drop_table('formula_versions')
    op.drop_index(op.f('ix_formula_ingredients_formula_id'), table_name='formula_ingredients')
    op.drop_table('formula_ingredients')
    op.drop_table('formulas')
