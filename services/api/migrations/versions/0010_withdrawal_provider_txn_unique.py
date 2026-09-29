"""make withdrawal payout references unique"""

from alembic import op
from sqlalchemy import inspect

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    constraints = {
        item["name"]
        for item in inspect(bind).get_unique_constraints("withdrawals")
    }
    if "uq_withdrawal_provider_txn" not in constraints:
        op.create_unique_constraint(
            "uq_withdrawal_provider_txn",
            "withdrawals",
            ["provider", "provider_txn_id"],
        )


def downgrade():
    bind = op.get_bind()
    constraints = {
        item["name"]
        for item in inspect(bind).get_unique_constraints("withdrawals")
    }
    if "uq_withdrawal_provider_txn" in constraints:
        op.drop_constraint(
            "uq_withdrawal_provider_txn",
            "withdrawals",
            type_="unique",
        )
