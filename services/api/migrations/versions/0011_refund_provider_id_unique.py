"""make provider refund ids unique"""

from alembic import op
from sqlalchemy import inspect

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    constraints = {
        item["name"]
        for item in inspect(bind).get_unique_constraints("refunds")
    }
    if "uq_refund_provider_refund_id" not in constraints:
        op.create_unique_constraint(
            "uq_refund_provider_refund_id",
            "refunds",
            ["provider", "provider_refund_id"],
        )


def downgrade():
    bind = op.get_bind()
    constraints = {
        item["name"]
        for item in inspect(bind).get_unique_constraints("refunds")
    }
    if "uq_refund_provider_refund_id" in constraints:
        op.drop_constraint(
            "uq_refund_provider_refund_id",
            "refunds",
            type_="unique",
        )
