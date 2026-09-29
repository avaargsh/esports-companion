"""add provider refund metadata"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {item["name"] for item in inspect(bind).get_columns("refunds")}
    if "out_refund_no" not in columns:
        op.add_column(
            "refunds",
            sa.Column("out_refund_no", sa.String(length=64), nullable=True),
        )
    if "raw_payload" not in columns:
        op.add_column(
            "refunds",
            sa.Column(
                "raw_payload",
                sa.JSON(),
                server_default=sa.text("'{}'::json"),
                nullable=False,
            ),
        )

    constraints = {
        item["name"]
        for item in inspect(bind).get_unique_constraints("refunds")
    }
    if "uq_refund_out_refund_no" not in constraints:
        op.create_unique_constraint(
            "uq_refund_out_refund_no",
            "refunds",
            ["out_refund_no"],
        )


def downgrade():
    bind = op.get_bind()
    columns = {item["name"] for item in inspect(bind).get_columns("refunds")}
    constraints = {
        item["name"]
        for item in inspect(bind).get_unique_constraints("refunds")
    }
    if "uq_refund_out_refund_no" in constraints:
        op.drop_constraint(
            "uq_refund_out_refund_no",
            "refunds",
            type_="unique",
        )
    if "raw_payload" in columns:
        op.drop_column("refunds", "raw_payload")
    if "out_refund_no" in columns:
        op.drop_column("refunds", "out_refund_no")
