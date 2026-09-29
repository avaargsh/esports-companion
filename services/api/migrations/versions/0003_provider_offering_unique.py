"""enforce one provider offering per player and sku"""

from alembic import op
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CONSTRAINT = "uq_provider_offering_player_sku"


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("provider_offerings"):
        return
    existing = {
        item.get("name")
        for item in inspect(bind).get_unique_constraints("provider_offerings")
    }
    if CONSTRAINT not in existing:
        op.create_unique_constraint(
            CONSTRAINT,
            "provider_offerings",
            ["player_id", "sku_id"],
        )


def downgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("provider_offerings"):
        return
    existing = {
        item.get("name")
        for item in inspect(bind).get_unique_constraints("provider_offerings")
    }
    if CONSTRAINT in existing:
        op.drop_constraint(
            CONSTRAINT,
            "provider_offerings",
            type_="unique",
        )
