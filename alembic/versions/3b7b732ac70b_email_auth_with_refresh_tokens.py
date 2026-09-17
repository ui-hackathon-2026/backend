"""email auth with refresh tokens

Revision ID: 3b7b732ac70b
Revises: 6ad16fc1b728
Create Date: 2026-09-17 22:46:11.005641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3b7b732ac70b'
down_revision: Union[str, Sequence[str], None] = '6ad16fc1b728'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('jti', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_jti'), 'refresh_tokens', ['jti'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.add_column('users', sa.Column('name', sa.String(length=100), nullable=False))
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=False))
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.drop_column('users', 'username')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('username', sa.VARCHAR(length=50), autoincrement=False, nullable=False))
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_username'), table_name='users', ['username'], unique=True)
    op.drop_column('users', 'email')
    op.drop_column('users', 'name')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_jti'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
