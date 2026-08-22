"""track pending purifier command

Revision ID: face8376ae98
Revises: 6cf8a92c06eb
Create Date: 2026-08-22 00:13:06.715455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'face8376ae98'
down_revision: Union[str, Sequence[str], None] = '6cf8a92c06eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("purifiers") as batch_op:
        batch_op.add_column(
            sa.Column("pending_command_id", sa.Uuid(), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("purifiers") as batch_op:
        batch_op.drop_column("pending_command_id")
