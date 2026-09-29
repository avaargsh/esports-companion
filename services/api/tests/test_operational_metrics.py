from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.db import SessionLocal
from app.metrics import (
    DISPUTES_OPEN,
    FINISH_REQUESTS_OLDEST_SECONDS,
    FINISH_REQUESTS_OVERDUE,
    FINISH_REQUESTS_PENDING,
    OPERATIONAL_METRICS_SCAN_SUCCESS,
    OUTBOX_OLDEST_PENDING_SECONDS,
    OUTBOX_PENDING,
    REFUNDS_INFLIGHT,
    WITHDRAWALS_PENDING,
)
from app.models import (
    Dispute,
    Game,
    Order,
    OutboxEvent,
    Refund,
    ServiceSKU,
    User,
    Wallet,
    Withdrawal,
)
from app.operational_metrics import refresh_operational_metrics


def test_operational_metrics_are_derived_from_postgres():
    now = datetime.now(timezone.utc)
    suffix = uuid4().hex[:8]

    with SessionLocal() as db:
        user = User(nickname=f"metrics-user-{suffix}")
        game = Game(
            code=f"metrics-{suffix}",
            name=f"Metrics {suffix}",
            status="ACTIVE",
        )
        db.add_all([user, game])
        db.flush()

        sku = ServiceSKU(
            game_id=game.id,
            name=f"Metrics SKU {suffix}",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=100,
            platform_fee_rate=Decimal("0.2000"),
            status="ACTIVE",
        )
        wallet = Wallet(user_id=user.id, available_balance=10000)
        db.add_all([sku, wallet])
        db.flush()

        order = Order(
            order_no=f"ORD_METRICS_{suffix.upper()}",
            user_id=user.id,
            game_id=game.id,
            sku_id=sku.id,
            status="DISPUTED",
            quantity=1,
            unit_price=100,
            total_amount=100,
            player_amount=80,
            platform_fee=20,
            remark="operational metrics fixture",
        )
        db.add(order)
        db.flush()

        finish_order = Order(
            order_no=f"ORD_FINISH_METRICS_{suffix.upper()}",
            user_id=user.id,
            game_id=game.id,
            sku_id=sku.id,
            status="FINISH_REQUESTED",
            quantity=1,
            unit_price=100,
            total_amount=100,
            player_amount=80,
            platform_fee=20,
            remark="finish request metrics fixture",
            finish_requested_at=now - timedelta(hours=1),
        )
        db.add(finish_order)
        db.flush()

        dispute = Dispute(
            order_id=order.id,
            status="OPEN",
            opened_by_user_id=user.id,
            opened_by_role="USER",
            reason_code="TEST",
            description="metrics",
            held_amount=100,
            idempotency_key=f"metrics-dispute-{suffix}",
        )
        db.add(dispute)
        db.flush()

        outbox = OutboxEvent(
            aggregate_type="ORDER",
            aggregate_id=str(order.id),
            event_type="TEST_EVENT",
            payload_json={},
            status="PENDING",
            created_at=now - timedelta(minutes=2),
        )
        refund = Refund(
            order_id=order.id,
            dispute_id=dispute.id,
            amount=100,
            status="PROCESSING",
            provider="WECHAT",
            out_refund_no=f"RFD_metrics_{suffix}",
            idempotency_key=f"metrics-refund-{suffix}",
            raw_payload={},
        )
        withdrawal = Withdrawal(
            user_id=user.id,
            wallet_id=wallet.id,
            amount=100,
            status="PENDING",
            provider="MANUAL",
            idempotency_key=f"metrics-withdrawal-{suffix}",
        )
        db.add_all([outbox, refund, withdrawal])
        db.commit()

    refresh_operational_metrics(now=now)

    assert OPERATIONAL_METRICS_SCAN_SUCCESS._value.get() == 1
    assert OUTBOX_PENDING._value.get() >= 1
    assert OUTBOX_OLDEST_PENDING_SECONDS._value.get() >= 120
    assert REFUNDS_INFLIGHT._value.get() >= 1
    assert WITHDRAWALS_PENDING._value.get() >= 1
    assert DISPUTES_OPEN._value.get() >= 1
    assert FINISH_REQUESTS_PENDING._value.get() >= 1
    assert FINISH_REQUESTS_OVERDUE._value.get() >= 1
    assert FINISH_REQUESTS_OLDEST_SECONDS._value.get() >= 3600
