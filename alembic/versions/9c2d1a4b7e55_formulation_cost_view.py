"""formulation cost view with frontend-identical weighting

Revision ID: 9c2d1a4b7e55
Revises: e08818f2c0d1
Create Date: 2026-09-18 07:10:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = '9c2d1a4b7e55'
down_revision: Union[str, Sequence[str], None] = 'e08818f2c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW formulation_cost_view AS
        SELECT
            f.id AS formula_id,
            f.name AS formula_name,
            ROUND(CAST(SUM(fi.weight_pct / 100.0 * COALESCE(fi.cost_idr_per_kg, 0.0)) AS numeric), 0) AS estimated_cogs_idr_per_kg,
            ROUND(CAST(SUM(fi.weight_pct / 100.0 * COALESCE(fi.tkdn_pct, 0.0)) AS numeric), 1) AS average_tkdn_pct,
            COUNT(fi.id) AS ingredient_count
        FROM formulas f
        LEFT JOIN formula_ingredients fi ON fi.formula_id = f.id
        GROUP BY f.id, f.name
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS formulation_cost_view")
