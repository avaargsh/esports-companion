"""add designated provider to orders"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {item["name"] for item in inspect(bind).get_columns("orders")}
    if "designated_player_id" not in columns:
        op.add_column(
            "orders",
            sa.Column(
                "designated_player_id",
                sa.Uuid(),
                sa.ForeignKey("player_profiles.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_orders_designated_player_id",
            "orders",
            ["designated_player_id"],
        )


def downgrade():
    bind = op.get_bind()
    columns = {item["name"] for item in inspect(bind).get_columns("orders")}
    if "designated_player_id" in columns:
        op.drop_index("ix_orders_designated_player_id", table_name="orders")
        op.drop_column("orders", "designated_player_id")
