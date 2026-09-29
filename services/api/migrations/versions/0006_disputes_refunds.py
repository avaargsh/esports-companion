"""add disputes and refunds"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("disputes"):
        op.create_table(
            "disputes",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("order_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("opened_by_user_id", sa.Uuid(), nullable=False),
            sa.Column("opened_by_role", sa.String(length=32), nullable=False),
            sa.Column("reason_code", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("held_amount", sa.Integer(), nullable=False),
            sa.Column("resolution", sa.String(length=64), nullable=True),
            sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.ForeignKeyConstraint(["opened_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id", name="uq_dispute_order"),
            sa.UniqueConstraint("idempotency_key", name="uq_dispute_idempotency"),
        )
        op.create_index("ix_disputes_order_id", "disputes", ["order_id"])
        op.create_index("ix_disputes_status", "disputes", ["status"])

    inspector = inspect(bind)
    if not inspector.has_table("refunds"):
        op.create_table(
            "refunds",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("order_id", sa.Uuid(), nullable=False),
            sa.Column("dispute_id", sa.Uuid(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_refund_id", sa.String(length=128), nullable=True),
            sa.Column("failure_reason", sa.String(length=256), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id", name="uq_refund_order"),
            sa.UniqueConstraint("dispute_id", name="uq_refund_dispute"),
            sa.UniqueConstraint("idempotency_key", name="uq_refund_idempotency"),
        )
        op.create_index("ix_refunds_order_id", "refunds", ["order_id"])
        op.create_index("ix_refunds_status", "refunds", ["status"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("refunds"):
        op.drop_index("ix_refunds_status", table_name="refunds")
        op.drop_index("ix_refunds_order_id", table_name="refunds")
        op.drop_table("refunds")
    inspector = inspect(bind)
    if inspector.has_table("disputes"):
        op.drop_index("ix_disputes_status", table_name="disputes")
        op.drop_index("ix_disputes_order_id", table_name="disputes")
        op.drop_table("disputes")
