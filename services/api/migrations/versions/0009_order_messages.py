"""add durable order messages"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("order_messages"):
        return

    op.create_table(
        "order_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("sender_role", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("client_message_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id",
            "sender_user_id",
            "client_message_id",
            name="uq_order_message_client_id",
        ),
    )
    op.create_index("ix_order_messages_order_id", "order_messages", ["order_id"])
    op.create_index(
        "ix_order_messages_sender_user_id",
        "order_messages",
        ["sender_user_id"],
    )
    op.create_index(
        "ix_order_messages_order_created",
        "order_messages",
        ["order_id", "created_at"],
    )


def downgrade():
    bind = op.get_bind()
    if inspect(bind).has_table("order_messages"):
        op.drop_index("ix_order_messages_order_created", table_name="order_messages")
        op.drop_index("ix_order_messages_sender_user_id", table_name="order_messages")
        op.drop_index("ix_order_messages_order_id", table_name="order_messages")
        op.drop_table("order_messages")
