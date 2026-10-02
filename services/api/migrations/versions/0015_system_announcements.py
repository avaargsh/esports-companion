"""add system announcements"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("system_announcements"):
        return

    op.create_table(
        "system_announcements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience", sa.String(length=32), nullable=False, server_default="ALL"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("operator_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_announcements_operator_user_id", "system_announcements", ["operator_user_id"])
    op.create_index("ix_system_announcements_status", "system_announcements", ["status"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("system_announcements"):
        return

    op.drop_index("ix_system_announcements_status", table_name="system_announcements")
    op.drop_index("ix_system_announcements_operator_user_id", table_name="system_announcements")
    op.drop_table("system_announcements")
