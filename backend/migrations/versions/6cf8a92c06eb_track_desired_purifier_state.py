"""track desired purifier state

Revision ID: 6cf8a92c06eb
Revises: 6d005d2f7023
Create Date: 2026-08-22 00:10:55.228833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cf8a92c06eb'
down_revision: Union[str, Sequence[str], None] = '6d005d2f7023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("purifiers") as batch_op:
        batch_op.add_column(
            sa.Column("desired_is_on", sa.Boolean(), nullable=True)
        )

    purifiers = sa.table(
        "purifiers",
        sa.column("is_on", sa.Boolean()),
        sa.column("desired_is_on", sa.Boolean()),
    )
    op.get_bind().execute(
        purifiers.update().values(desired_is_on=purifiers.c.is_on)
    )

    with op.batch_alter_table("purifiers") as batch_op:
        batch_op.alter_column(
            "desired_is_on",
            existing_type=sa.Boolean(),
            nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("purifiers") as batch_op:
        batch_op.drop_column("desired_is_on")
