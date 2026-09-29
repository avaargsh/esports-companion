from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db import SessionLocal
from app.metrics import (
    DISPUTES_OPEN,
    OPERATIONAL_METRICS_SCAN_SUCCESS,
    OUTBOX_OLDEST_PENDING_SECONDS,
    OUTBOX_PENDING,
    REFUNDS_INFLIGHT,
    WITHDRAWALS_PENDING,
)
from app.models import Dispute, OutboxEvent, Refund, User, Withdrawal, Wallet
from app.operational_metrics import refresh_operational_metrics


def test_operational_metrics_are_derived_from_postgres():
    now = datetime.now(timezone.utc)
    suffix = uuid4().hex[:8]

    with SessionLocal() as db:
        user = User(nickname=f"metrics-user-{suffix}")
        db.add(user)
        db.flush()
        wallet = Wallet(user_id=user.id, available_balance=10000)
        db.add(wallet)
        db.flush()

        outbox = OutboxEvent(
            aggregate_type="ORDER",
            aggregate_id=uuid4().hex,
            event_type="TEST_EVENT",
            payload_json={},
            status="PENDING",
            created_at=now - timedelta(minutes=2),
        )
        dispute = Dispute(
            order_id=uuid4(),
            status="OPEN",
            opened_by_user_id=user.id,
            opened_by_role="USER",
            reason_code="TEST",
            description="metrics",
            held_amount=100,
            idempotency_key=f"metrics-dispute-{suffix}",
        )
        refund = Refund(
            order_id=uuid4(),
            dispute_id=uuid4(),
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
        db.add_all([outbox, dispute, refund, withdrawal])
        db.commit()

    refresh_operational_metrics(now=now)

    assert OPERATIONAL_METRICS_SCAN_SUCCESS._value.get() == 1
    assert OUTBOX_PENDING._value.get() >= 1
    assert OUTBOX_OLDEST_PENDING_SECONDS._value.get() >= 120
    assert REFUNDS_INFLIGHT._value.get() >= 1
    assert WITHDRAWALS_PENDING._value.get() >= 1
    assert DISPUTES_OPEN._value.get() >= 1
