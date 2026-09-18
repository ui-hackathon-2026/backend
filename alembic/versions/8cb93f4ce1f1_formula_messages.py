"""formula messages

Revision ID: 8cb93f4ce1f1
Revises: 9c2d1a4b7e55
Create Date: 2026-09-18 07:31:40.550208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8cb93f4ce1f1'
down_revision: Union[str, Sequence[str], None] = '9c2d1a4b7e55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('formula_messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('formula_id', sa.String(length=64), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=True),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('proposal', sa.JSON(), nullable=True),
    sa.Column('linked_artifact_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['formula_id'], ['formulas.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_formula_messages_formula_id'), 'formula_messages', ['formula_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_formula_messages_formula_id'), table_name='formula_messages')
    op.drop_table('formula_messages')
