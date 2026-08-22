"""track sensor message ids

Revision ID: 64597b22d38c
Revises: face8376ae98
Create Date: 2026-08-22 00:33:15.607711

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64597b22d38c'
down_revision: Union[str, Sequence[str], None] = 'face8376ae98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("sensor_readings") as batch_op:
        batch_op.add_column(
            sa.Column("source_message_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_sensor_readings_source_message_id",
            ["source_message_id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sensor_readings") as batch_op:
        batch_op.drop_constraint(
            "uq_sensor_readings_source_message_id",
            type_="unique",
        )
        batch_op.drop_column("source_message_id")
