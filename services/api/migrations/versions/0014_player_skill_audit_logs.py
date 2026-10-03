"""add player skill audit logs"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("player_skill_audit_logs"):
        return

    op.create_table(
        "player_skill_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("operator_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["player_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_player_skill_audit_logs_action", "player_skill_audit_logs", ["action"])
    op.create_index("ix_player_skill_audit_logs_operator_user_id", "player_skill_audit_logs", ["operator_user_id"])
    op.create_index("ix_player_skill_audit_logs_skill_id", "player_skill_audit_logs", ["skill_id"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("player_skill_audit_logs"):
        return

    op.drop_index("ix_player_skill_audit_logs_skill_id", table_name="player_skill_audit_logs")
    op.drop_index("ix_player_skill_audit_logs_operator_user_id", table_name="player_skill_audit_logs")
    op.drop_index("ix_player_skill_audit_logs_action", table_name="player_skill_audit_logs")
    op.drop_table("player_skill_audit_logs")
