"""add room devices

Revision ID: 6d005d2f7023
Revises: 804037092d91
Create Date: 2026-08-21 22:49:46.393976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d005d2f7023'
down_revision: Union[str, Sequence[str], None] = '804037092d91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rooms",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_rooms_name_lower",
        "rooms",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "sensors",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id"),
    )
    op.create_table(
        "purifiers",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("is_on", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id"),
    )

    with op.batch_alter_table("sensor_readings") as batch_op:
        batch_op.add_column(
            sa.Column("sensor_id", sa.BigInteger(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_sensor_readings_sensor_id_sensors",
            "sensors",
            ["sensor_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_sensor_readings_sensor_id",
            ["sensor_id"],
        )

    sensor_readings = sa.table(
        "sensor_readings",
        sa.column("sensor_id", sa.BigInteger()),
    )
    connection = op.get_bind()
    reading_count = connection.scalar(
        sa.select(sa.func.count()).select_from(sensor_readings)
    )

    if reading_count:
        rooms = sa.table(
            "rooms",
            sa.column("id", sa.BigInteger()),
            sa.column("name", sa.String()),
        )
        sensors = sa.table(
            "sensors",
            sa.column("id", sa.BigInteger()),
            sa.column("room_id", sa.BigInteger()),
        )
        purifiers = sa.table(
            "purifiers",
            sa.column("id", sa.BigInteger()),
            sa.column("room_id", sa.BigInteger()),
            sa.column("is_on", sa.Boolean()),
        )
        op.bulk_insert(rooms, [{"id": 1, "name": "Legacy Room"}])
        op.bulk_insert(sensors, [{"id": 1, "room_id": 1}])
        op.bulk_insert(
            purifiers,
            [{"id": 1, "room_id": 1, "is_on": False}],
        )
        connection.execute(sensor_readings.update().values(sensor_id=1))

    with op.batch_alter_table("sensor_readings") as batch_op:
        batch_op.alter_column(
            "sensor_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sensor_readings") as batch_op:
        batch_op.drop_index("ix_sensor_readings_sensor_id")
        batch_op.drop_constraint(
            "fk_sensor_readings_sensor_id_sensors",
            type_="foreignkey",
        )
        batch_op.drop_column("sensor_id")

    op.drop_table("purifiers")
    op.drop_table("sensors")
    op.drop_index("uq_rooms_name_lower", table_name="rooms")
    op.drop_table("rooms")
