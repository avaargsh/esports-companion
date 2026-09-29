"""add player skill verification metadata"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

UNIQUE_NAME = "uq_player_skill_player_game"


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {item["name"] for item in inspector.get_columns("player_skills")}

    if "evidence_url" not in columns:
        op.add_column(
            "player_skills",
            sa.Column("evidence_url", sa.String(length=512), nullable=True),
        )
    if "verification_status" not in columns:
        op.add_column(
            "player_skills",
            sa.Column(
                "verification_status",
                sa.String(length=32),
                nullable=False,
                server_default="PENDING",
            ),
        )
        op.create_index(
            "ix_player_skills_verification_status",
            "player_skills",
            ["verification_status"],
        )
    if "review_note" not in columns:
        op.add_column(
            "player_skills",
            sa.Column(
                "review_note",
                sa.Text(),
                nullable=False,
                server_default="",
            ),
        )

    uniques = {
        item.get("name")
        for item in inspect(bind).get_unique_constraints("player_skills")
    }
    if UNIQUE_NAME not in uniques:
        op.create_unique_constraint(
            UNIQUE_NAME,
            "player_skills",
            ["player_id", "game_id"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    uniques = {
        item.get("name")
        for item in inspector.get_unique_constraints("player_skills")
    }
    if UNIQUE_NAME in uniques:
        op.drop_constraint(UNIQUE_NAME, "player_skills", type_="unique")

    columns = {item["name"] for item in inspect(bind).get_columns("player_skills")}
    if "review_note" in columns:
        op.drop_column("player_skills", "review_note")
    if "verification_status" in columns:
        op.drop_index("ix_player_skills_verification_status", table_name="player_skills")
        op.drop_column("player_skills", "verification_status")
    if "evidence_url" in columns:
        op.drop_column("player_skills", "evidence_url")
