"""add admin menu icons"""

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

DEFAULT_MENU_ICONS = [
    ("dashboard", "概览", "http://localhost:9000/esports-images/admin-icons/dashboard.svg", 10),
    ("orders", "订单", "http://localhost:9000/esports-images/admin-icons/orders.svg", 20),
    ("players", "陪玩", "http://localhost:9000/esports-images/admin-icons/players.svg", 30),
    ("finance", "资金", "http://localhost:9000/esports-images/admin-icons/finance.svg", 40),
    ("config", "配置", "http://localhost:9000/esports-images/admin-icons/config.svg", 50),
]


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("admin_menu_icons"):
        op.create_table(
            "admin_menu_icons",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("menu_key", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=32), nullable=False),
            sa.Column("icon_url", sa.String(length=512), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("menu_key", name="uq_admin_menu_icons_key"),
        )
        op.create_index("ix_admin_menu_icons_menu_key", "admin_menu_icons", ["menu_key"])
        op.create_index("ix_admin_menu_icons_status", "admin_menu_icons", ["status"])

    for key, label, icon_url, sort_order in DEFAULT_MENU_ICONS:
        bind.execute(
            text(
                """
                INSERT INTO admin_menu_icons (id, menu_key, label, icon_url, sort_order, status)
                VALUES (:id, :menu_key, :label, :icon_url, :sort_order, 'ACTIVE')
                ON CONFLICT (menu_key) DO NOTHING
                """
            ),
            {
                "id": uuid.uuid4(),
                "menu_key": key,
                "label": label,
                "icon_url": icon_url,
                "sort_order": sort_order,
            },
        )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("admin_menu_icons"):
        op.drop_index("ix_admin_menu_icons_status", table_name="admin_menu_icons")
        op.drop_index("ix_admin_menu_icons_menu_key", table_name="admin_menu_icons")
        op.drop_table("admin_menu_icons")
