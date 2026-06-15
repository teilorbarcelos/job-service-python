"""add_session_version_and_security_fields

Revision ID: 923509e24aee
Revises: aaa5f275344d
Create Date: 2026-06-08 21:32:56.746365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '923509e24aee'
down_revision: Union[str, Sequence[str], None] = 'aaa5f275344d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('auth', sa.Column('password_algo', sa.String(length=20), nullable=True))
    op.execute("UPDATE auth SET password_algo = 'bcrypt' WHERE password_algo IS NULL")
    op.alter_column('auth', 'password_algo', nullable=False, server_default='bcrypt')

    op.add_column('auth', sa.Column('password_updated_at', sa.DateTime(), nullable=True))

    op.add_column('auth', sa.Column('session_version', sa.Integer(), nullable=True, server_default=sa.text('1')))
    op.execute("UPDATE auth SET session_version = 1 WHERE session_version IS NULL")
    op.alter_column('auth', 'session_version', nullable=False, server_default=sa.text('1'))

    op.drop_constraint(op.f('user_cognito_id_key'), 'user', type_='unique')
    op.create_index('ix_user_email_is_deleted', 'user', ['email', 'is_deleted'], unique=False)
    op.drop_column('user', 'cognito_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('user', sa.Column('cognito_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.drop_index('ix_user_email_is_deleted', table_name='user')
    op.create_unique_constraint(op.f('user_cognito_id_key'), 'user', ['cognito_id'], postgresql_nulls_not_distinct=False)
    op.drop_column('auth', 'session_version')
    op.drop_column('auth', 'password_updated_at')
    op.drop_column('auth', 'password_algo')
    op.drop_column('auth', 'password_updated_at')
    op.drop_column('auth', 'password_algo')
    op.create_table('alembic_version',
    sa.Column('version_num', sa.VARCHAR(length=32), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('version_num', name=op.f('alembic_version_pkc'))
    )
    # ### end Alembic commands ###
