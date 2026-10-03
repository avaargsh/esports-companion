"""store provider session key for phone binding"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("auth_sessions")}
    if "provider_session_key" not in columns:
        op.add_column(
            "auth_sessions",
            sa.Column("provider_session_key", sa.String(length=256), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("auth_sessions")}
    if "provider_session_key" in columns:
        op.drop_column("auth_sessions", "provider_session_key")
