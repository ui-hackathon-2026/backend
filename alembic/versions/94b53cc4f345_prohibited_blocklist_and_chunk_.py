"""prohibited blocklist and chunk enrichment

Revision ID: 94b53cc4f345
Revises: e77acdd9bacd
Create Date: 2026-09-18 01:45:04.984458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '94b53cc4f345'
down_revision: Union[str, Sequence[str], None] = 'e77acdd9bacd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('prohibited_substances',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=512), nullable=False),
    sa.Column('cas_number', sa.String(length=64), nullable=True),
    sa.Column('entry_no', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prohibited_substances_name'), 'prohibited_substances', ['name'], unique=False)
    op.add_column('knowledge_chunks', sa.Column('acd_number', sa.String(length=32), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('concentration_note_raw', sa.Text(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('extraction_confidence', sa.Float(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('chunk_type', sa.String(length=64), nullable=True))
    op.alter_column('knowledge_chunks', 'inci_name',
               existing_type=sa.VARCHAR(length=255),
                nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('knowledge_chunks', 'inci_name',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.drop_column('knowledge_chunks', 'chunk_type')
    op.drop_column('knowledge_chunks', 'extraction_confidence')
    op.drop_column('knowledge_chunks', 'concentration_note_raw')
    op.drop_column('knowledge_chunks', 'acd_number')
    op.drop_index(op.f('ix_prohibited_substances_name'), table_name='prohibited_substances')
    op.drop_table('prohibited_substances')
