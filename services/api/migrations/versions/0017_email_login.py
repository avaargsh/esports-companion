"""add email login support"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "email" not in user_columns:
            op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
        indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_email" not in indexes:
            op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not inspector.has_table("email_verification_codes"):
        op.create_table(
            "email_verification_codes",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("purpose", sa.String(length=32), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("email_verification_codes")}
    if "ix_email_verification_codes_email" not in indexes:
        op.create_index("ix_email_verification_codes_email", "email_verification_codes", ["email"])
    if "ix_email_verification_codes_purpose" not in indexes:
        op.create_index("ix_email_verification_codes_purpose", "email_verification_codes", ["purpose"])
    if "ix_email_verification_codes_code_hash" not in indexes:
        op.create_index("ix_email_verification_codes_code_hash", "email_verification_codes", ["code_hash"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("email_verification_codes"):
        op.drop_table("email_verification_codes")
    if inspector.has_table("users"):
        indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_email" in indexes:
            op.drop_index("ix_users_email", table_name="users")
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "email" in columns:
            op.drop_column("users", "email")
