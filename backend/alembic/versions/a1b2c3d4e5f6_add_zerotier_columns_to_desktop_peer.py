"""add zerotier columns to desktop peer

Revision ID: a1b2c3d4e5f6
Revises: 64aa506f4ebc
Create Date: 2026-07-22 15:24:28.888847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '64aa506f4ebc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('desktop_peers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('zerotier_node_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('zt_ip', sa.String(), nullable=True))
        batch_op.alter_column('public_key', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('desktop_peers', schema=None) as batch_op:
        batch_op.alter_column('public_key', existing_type=sa.String(), nullable=False)
        batch_op.drop_column('zt_ip')
        batch_op.drop_column('zerotier_node_id')
