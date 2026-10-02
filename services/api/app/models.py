import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .status_labels import (
    COMMON_STATUS_TEXT,
    DISPUTE_STATUS_TEXT,
    ORDER_STATUS_TEXT,
    PLAYER_SKILL_STATUS_TEXT,
    PLAYER_VERIFICATION_STATUS_TEXT,
    SERVICE_STATUS_TEXT,
    status_text,
)


def new_uuid():
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    openid: Mapped[str | None] = mapped_column(String(128), unique=True)
    unionid: Mapped[str | None] = mapped_column(String(128))
    nickname: Mapped[str] = mapped_column(String(80), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(32), default="USER")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("auth_sessions.id")
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_session_key: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminMenuIcon(Base, TimestampMixin):
    __tablename__ = "admin_menu_icons"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    menu_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(32))
    icon_url: Mapped[str] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def status_text(self) -> str:
        return status_text(self.status, COMMON_STATUS_TEXT)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)


class Game(Base, TimestampMixin):
    __tablename__ = "games"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    icon_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class PlayerProfile(Base, TimestampMixin):
    __tablename__ = "player_profiles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    bio: Mapped[str] = mapped_column(Text, default="")
    gender: Mapped[str | None] = mapped_column(String(32))
    verification_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    service_status: Mapped[str] = mapped_column(String(32), default="OFFLINE")
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def verification_status_text(self) -> str:
        return status_text(self.verification_status, PLAYER_VERIFICATION_STATUS_TEXT)

    @property
    def service_status_text(self) -> str:
        return status_text(self.service_status, SERVICE_STATUS_TEXT)


class PlayerSkill(Base, TimestampMixin):
    __tablename__ = "player_skills"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="uq_player_skill_player_game"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("player_profiles.id"))
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id"))
    rank: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_url: Mapped[str | None] = mapped_column(String(512))
    verification_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")

    @property
    def verification_status_text(self) -> str:
        return status_text(self.verification_status, PLAYER_SKILL_STATUS_TEXT)

    @property
    def status_text(self) -> str:
        return status_text(self.status, COMMON_STATUS_TEXT)


class PlayerSkillAuditLog(Base):
    __tablename__ = "player_skill_audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("player_skills.id"), index=True)
    operator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceSKU(Base, TimestampMixin):
    __tablename__ = "service_skus"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id"))
    name: Mapped[str] = mapped_column(String(120))
    service_type: Mapped[str] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(32), default="SESSION")
    duration_minutes: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    platform_fee_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.2000"))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderOffering(Base, TimestampMixin):
    __tablename__ = "provider_offerings"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "sku_id",
            name="uq_provider_offering_player_sku",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("player_profiles.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_skus.id"))
    price_override: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_skus.id"))
    designated_player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("player_profiles.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="WAITING_PAYMENT", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[int] = mapped_column(Integer)
    player_amount: Mapped[int] = mapped_column(Integer, default=0)
    platform_fee: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str] = mapped_column(Text, default="")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finish_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def status_text(self) -> str:
        return status_text(self.status, ORDER_STATUS_TEXT)


class OrderAssignment(Base, TimestampMixin):
    __tablename__ = "order_assignments"
    __table_args__ = (
        Index(
            "uq_order_active_assignment",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("player_profiles.id"))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    assigned_by: Mapped[str] = mapped_column(String(32), default="PLAYER")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(String(128))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def from_status_text(self) -> str:
        return status_text(self.from_status, ORDER_STATUS_TEXT)

    @property
    def to_status_text(self) -> str:
        return status_text(self.to_status, ORDER_STATUS_TEXT)


class OrderMessage(Base):
    __tablename__ = "order_messages"
    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "sender_user_id",
            "client_message_id",
            name="uq_order_message_client_id",
        ),
        Index("ix_order_messages_order_created", "order_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    sender_role: Mapped[str] = mapped_column(String(32))
    message_type: Mapped[str] = mapped_column(String(32), default="TEXT")
    content: Mapped[str] = mapped_column(Text)
    client_message_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PaymentTransaction(Base, TimestampMixin):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_txn_id", name="uq_payment_provider_txn"),
        UniqueConstraint("idempotency_key", name="uq_payment_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    provider: Mapped[str] = mapped_column(String(32))
    provider_txn_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    available_balance: Mapped[int] = mapped_column(Integer, default=0)
    frozen_balance: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallets.id"))
    biz_type: Mapped[str] = mapped_column(String(64))
    biz_id: Mapped[str] = mapped_column(String(128))
    entry_type: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Withdrawal(Base, TimestampMixin):
    __tablename__ = "withdrawals"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_withdrawal_idempotency"),
        UniqueConstraint(
            "provider",
            "provider_txn_id",
            name="uq_withdrawal_provider_txn",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    wallet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallets.id"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="MANUAL")
    provider_txn_id: Mapped[str | None] = mapped_column(String(128))
    failure_reason: Mapped[str | None] = mapped_column(String(256))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def status_text(self) -> str:
        return status_text(self.status, COMMON_STATUS_TEXT)


class Settlement(Base, TimestampMixin):
    __tablename__ = "settlements"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_settlement_idempotency"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("player_profiles.id"))
    gross_amount: Mapped[int] = mapped_column(Integer)
    player_amount: Mapped[int] = mapped_column(Integer)
    platform_fee: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def status_text(self) -> str:
        return status_text(self.status, COMMON_STATUS_TEXT)


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("order_id", name="uq_review_order"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("player_profiles.id"))
    rating: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, default="")


class SystemAnnouncement(Base, TimestampMixin):
    __tablename__ = "system_announcements"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(32), default="ALL")
    notice_type: Mapped[str] = mapped_column(String(32), default="NORMAL", index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    operator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def status_text(self) -> str:
        return status_text(
            self.status,
            {"DRAFT": "草稿", "PUBLISHED": "已发布", "OFFLINE": "已下线"},
        )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    aggregate_type: Mapped[str] = mapped_column(String(64))
    aggregate_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dispute(Base, TimestampMixin):
    __tablename__ = "disputes"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_dispute_order"),
        UniqueConstraint("idempotency_key", name="uq_dispute_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    opened_by_role: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    held_amount: Mapped[int] = mapped_column(Integer)
    resolution: Mapped[str | None] = mapped_column(String(64))
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128))

    @property
    def status_text(self) -> str:
        return status_text(self.status, DISPUTE_STATUS_TEXT)


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_refund_order"),
        UniqueConstraint("dispute_id", name="uq_refund_dispute"),
        UniqueConstraint("idempotency_key", name="uq_refund_idempotency"),
        UniqueConstraint("out_refund_no", name="uq_refund_out_refund_no"),
        UniqueConstraint(
            "provider",
            "provider_refund_id",
            name="uq_refund_provider_refund_id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    dispute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disputes.id"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="MANUAL")
    out_refund_no: Mapped[str | None] = mapped_column(String(64))
    provider_refund_id: Mapped[str | None] = mapped_column(String(128))
    failure_reason: Mapped[str | None] = mapped_column(String(256))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
