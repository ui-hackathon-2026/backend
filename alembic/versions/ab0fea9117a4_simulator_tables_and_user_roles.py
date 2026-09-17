"""simulator tables and user roles

Revision ID: ab0fea9117a4
Revises: d3da69b38105
Create Date: 2026-09-17 18:40:11.303873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ab0fea9117a4'
down_revision: Union[str, Sequence[str], None] = 'd3da69b38105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('ingredients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('inci', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('smiles', sa.String(length=1024), nullable=False),
    sa.Column('default_phase', sa.String(length=1), nullable=False),
    sa.Column('default_role', sa.String(length=32), nullable=False),
    sa.Column('hlb', sa.Float(), nullable=True),
    sa.Column('cost_per_kg_idr', sa.Float(), nullable=False),
    sa.Column('tkdn_pct', sa.Float(), nullable=False),
    sa.Column('bpom_limit_pct', sa.Float(), nullable=True),
    sa.Column('halal_status', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingredients_inci'), 'ingredients', ['inci'], unique=True)
    op.create_table('simulation_runs',
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('formula_id', sa.String(length=64), nullable=True),
    sa.Column('formula_name', sa.String(length=255), nullable=False),
    sa.Column('temperature_c', sa.Float(), nullable=False),
    sa.Column('duration_days', sa.Integer(), nullable=False),
    sa.Column('engine_used', sa.String(length=32), nullable=False),
    sa.Column('stability_score', sa.Float(), nullable=False),
    sa.Column('verdict', sa.String(length=64), nullable=False),
    sa.Column('mean_droplet_size_nm', sa.Float(), nullable=False),
    sa.Column('dynamic_viscosity_mpas', sa.Float(), nullable=False),
    sa.Column('is_out_of_distribution', sa.Boolean(), nullable=False),
    sa.Column('raw_response', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(op.f('ix_simulation_runs_formula_id'), 'simulation_runs', ['formula_id'], unique=False)
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='formulator', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'role')
    op.drop_index(op.f('ix_simulation_runs_formula_id'), table_name='simulation_runs')
    op.drop_table('simulation_runs')
    op.drop_index(op.f('ix_ingredients_inci'), table_name='ingredients')
    op.drop_table('ingredients')
