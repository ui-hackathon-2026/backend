"""formula project link

Revision ID: d14f817704d1
Revises: 608d042612a6
Create Date: 2026-09-18 02:06:16.861089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd14f817704d1'
down_revision: Union[str, Sequence[str], None] = '608d042612a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('formulas', sa.Column('project_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_formulas_project_id'), 'formulas', ['project_id'], unique=False)
    op.create_foreign_key('formulas_project_id_fkey', 'formulas', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('formulas_project_id_fkey', 'formulas', type_='foreignkey')
    op.drop_index(op.f('ix_formulas_project_id'), table_name='formulas')
    op.drop_column('formulas', 'project_id')
