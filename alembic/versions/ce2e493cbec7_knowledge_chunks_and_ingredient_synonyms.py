"""knowledge chunks and ingredient synonyms

Revision ID: ce2e493cbec7
Revises: 383a10a7e482
Create Date: 2026-09-17 21:48:40.558995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ce2e493cbec7'
down_revision: Union[str, Sequence[str], None] = '383a10a7e482'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('knowledge_chunks',
    sa.Column('id', sa.String(length=128), nullable=False),
    sa.Column('title', sa.String(length=512), nullable=False),
    sa.Column('regulation', sa.String(length=255), nullable=False),
    sa.Column('appendix', sa.String(length=255), nullable=False),
    sa.Column('clause_entry', sa.String(length=128), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('substance_name', sa.String(length=255), nullable=False),
    sa.Column('inci_name', sa.String(length=255), nullable=False),
    sa.Column('synonyms', sa.JSON(), nullable=False),
    sa.Column('cas_number', sa.String(length=64), nullable=True),
    sa.Column('max_concentration_pct', sa.Float(), nullable=True),
    sa.Column('allowed_product_types', sa.JSON(), nullable=False),
    sa.Column('conditions_of_use', sa.Text(), nullable=False),
    sa.Column('mandatory_warnings', sa.JSON(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('halal_critical_point', sa.Text(), nullable=True),
    sa.Column('source_url', sa.String(length=512), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_chunks_inci_name'), 'knowledge_chunks', ['inci_name'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_substance_name'), 'knowledge_chunks', ['substance_name'], unique=False)
    op.add_column('ingredients', sa.Column('synonyms', sa.JSON(), nullable=True))
    op.execute("UPDATE ingredients SET synonyms = '[]' WHERE synonyms IS NULL")
    op.alter_column('ingredients', 'synonyms', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ingredients', 'synonyms')
    op.drop_index(op.f('ix_knowledge_chunks_substance_name'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_inci_name'), table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
