from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    Dispute,
    Game,
    PaymentTransaction,
    Refund,
    ServiceSKU,
    User,
)
from app.providers.refund import RefundIntent
from app.services.order_service import OrderService
from app.services.refund_service import RefundService


class QueryProvider:
    name = "WECHAT"

    def __init__(
        self,
        *,
        order_no: str,
        provider_txn_id: str,
        total_amount: int = 3000,
        refund_amount: int = 3000,
    ):
        self.order_no = order_no
        self.provider_txn_id = provider_txn_id
        self.total_amount = total_amount
        self.refund_amount = refund_amount

    def create_refund(self, **_kwargs):
        raise AssertionError("create_refund must not run during reconciliation")

    def query_refund(self, *, refund):
        return RefundIntent(
            provider=self.name,
            provider_refund_id="wx-refund-query-1",
            status="SUCCESS",
            raw_payload={
                "refund_id": "wx-refund-query-1",
                "out_refund_no": refund.out_refund_no,
                "transaction_id": self.provider_txn_id,
                "out_trade_no": self.order_no,
                "status": "SUCCESS",
                "amount": {
                    "total": self.total_amount,
                    "refund": self.refund_amount,
                },
            },
        )


def _fixture():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()

    suffix = uuid4().hex[:8]
    customer = User(nickname=f"refund-customer-{suffix}")
    platform = User(nickname=f"refund-platform-{suffix}", role="PLATFORM")
    game = Game(code=f"refund-{suffix}", name="Refund Reconcile")
    db.add_all([customer, platform, game])
    db.flush()

    sku = ServiceSKU(
        game_id=game.id,
        name="Refund SKU",
        service_type="ENTERTAINMENT",
        duration_minutes=60,
        price=3000,
        platform_fee_rate=Decimal("0.2000"),
    )
    db.add(sku)
    db.commit()

    order = OrderService.create_order(
        db,
        user_id=customer.id,
        sku_id=sku.id,
    )
    order.status = "REFUNDING"

    payment = PaymentTransaction(
        order_id=order.id,
        provider="WECHAT",
        provider_txn_id="wx-pay-query-1",
        idempotency_key=f"pay-{suffix}",
        amount=3000,
        status="SUCCESS",
        raw_payload={},
    )
    dispute = Dispute(
        order_id=order.id,
        status="RESOLVING",
        opened_by_user_id=customer.id,
        opened_by_role="USER",
        reason_code="CANCEL_BEFORE_SERVICE",
        description="refund reconciliation",
        held_amount=3000,
        resolution="REFUND_CUSTOMER",
        resolved_by_user_id=platform.id,
        idempotency_key=f"dispute-{suffix}",
    )
    db.add_all([payment, dispute])
    db.flush()

    refund = Refund(
        order_id=order.id,
        dispute_id=dispute.id,
        amount=3000,
        status="SUBMITTING",
        provider="WECHAT",
        out_refund_no=f"RFD_{suffix}",
        provider_refund_id=None,
        idempotency_key=f"refund-{suffix}",
        raw_payload={"submit": {"status": "PROCESSING"}},
    )
    db.add(refund)
    db.commit()
    return db, order, dispute, refund, payment


def test_submitting_refund_recovers_to_refunded_from_signed_provider_truth():
    db, order, dispute, refund, payment = _fixture()
    try:
        provider = QueryProvider(
            order_no=order.order_no,
            provider_txn_id=payment.provider_txn_id,
        )

        result = RefundService.reconcile(
            db,
            refund_id=refund.id,
            provider=provider,
        )

        assert result.status == "COMPLETED"
        assert result.provider_refund_id == "wx-refund-query-1"
        assert result.raw_payload["query"]["status"] == "SUCCESS"
        assert order.status == "REFUNDED"
        assert dispute.status == "RESOLVED"
    finally:
        db.close()


def test_reconciliation_rejects_amount_mismatch_before_completing_order():
    db, order, dispute, refund, payment = _fixture()
    try:
        provider = QueryProvider(
            order_no=order.order_no,
            provider_txn_id=payment.provider_txn_id,
            refund_amount=2999,
        )

        with pytest.raises(ValueError, match="REFUND_QUERY_AMOUNT_MISMATCH"):
            RefundService.reconcile(
                db,
                refund_id=refund.id,
                provider=provider,
            )

        db.rollback()
        db.refresh(order)
        db.refresh(refund)
        db.refresh(dispute)
        assert order.status == "REFUNDING"
        assert refund.status == "SUBMITTING"
        assert dispute.status == "RESOLVING"
    finally:
        db.close()


def test_reconciliation_requires_matching_wechat_payment():
    db, order, _dispute, refund, payment = _fixture()
    try:
        payment.provider = "MOCK"
        db.commit()

        provider = QueryProvider(
            order_no=order.order_no,
            provider_txn_id="wx-pay-query-1",
        )
        with pytest.raises(ValueError, match="SUCCESSFUL_PAYMENT_NOT_FOUND"):
            RefundService.reconcile(
                db,
                refund_id=refund.id,
                provider=provider,
            )
    finally:
        db.close()
