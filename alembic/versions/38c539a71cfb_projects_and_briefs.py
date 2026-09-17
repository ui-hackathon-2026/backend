"""projects and briefs

Revision ID: 38c539a71cfb
Revises: acf38401ddfc
Create Date: 2026-09-17 20:49:06.947854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '38c539a71cfb'
down_revision: Union[str, Sequence[str], None] = 'acf38401ddfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('briefs',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('content_text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('projects',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('brief_text', sa.Text(), nullable=True),
    sa.Column('brief_id', sa.String(length=64), nullable=True),
    sa.Column('ref_formula_id', sa.String(length=64), nullable=True),
    sa.Column('instruction', sa.Text(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['brief_id'], ['briefs.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ref_formula_id'], ['formulas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('projects')
    op.drop_table('briefs')
