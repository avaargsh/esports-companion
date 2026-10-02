"""add system announcement notice type"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("system_announcements"):
        return

    columns = {column["name"] for column in inspector.get_columns("system_announcements")}
    if "notice_type" not in columns:
        op.add_column(
            "system_announcements",
            sa.Column("notice_type", sa.String(length=32), nullable=False, server_default="NORMAL"),
        )
    indexes = {index["name"] for index in inspector.get_indexes("system_announcements")}
    if "ix_system_announcements_notice_type" not in indexes:
        op.create_index("ix_system_announcements_notice_type", "system_announcements", ["notice_type"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("system_announcements"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("system_announcements")}
    if "ix_system_announcements_notice_type" in indexes:
        op.drop_index("ix_system_announcements_notice_type", table_name="system_announcements")
    columns = {column["name"] for column in inspector.get_columns("system_announcements")}
    if "notice_type" in columns:
        op.drop_column("system_announcements", "notice_type")
