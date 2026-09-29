import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Game, PaymentTransaction, ServiceSKU, User
from app.providers.payment import PaymentIntent
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService


class SlowPendingProvider:
    name = "WECHAT"

    def __init__(self):
        self.calls = 0
        self._lock = threading.Lock()

    def create_payment(self, *, order, idempotency_key, payer_subject=None):
        with self._lock:
            self.calls += 1
            call_number = self.calls
        time.sleep(0.2)
        return PaymentIntent(
            provider=self.name,
            provider_txn_id=f"prepay-{call_number}-{uuid.uuid4().hex}",
            status="PENDING",
            raw_payload={"idempotencyKey": idempotency_key},
            client_payload={"package": f"prepay_id=prepay-{call_number}"},
        )


def test_concurrent_payment_attempts_create_only_one_provider_payment():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        user = User(openid=f"openid-{suffix}", nickname="payment-race-customer")
        game = Game(code=f"pay-race-{suffix}", name="Payment Race")
        db.add_all([user, game])
        db.flush()
        sku = ServiceSKU(
            game_id=game.id,
            name="Concurrent Payment SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add(sku)
        db.commit()

        order = OrderService.create_order(db, user_id=user.id, sku_id=sku.id)
        order_id = order.id

    provider = SlowPendingProvider()
    barrier = threading.Barrier(2)

    def prepare(key: str):
        with SessionLocal() as db:
            order = OrderService.get(db, order_id)
            barrier.wait(timeout=5)
            try:
                PaymentService.prepare_payment(
                    db,
                    order=order,
                    provider=provider,
                    idempotency_key=key,
                )
                return "success"
            except ValueError as exc:
                db.rollback()
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(prepare, "payment-race-a"),
            pool.submit(prepare, "payment-race-b"),
        ]
        results = [future.result(timeout=10) for future in futures]

    assert results.count("success") == 1
    assert results.count("PAYMENT_ATTEMPT_ALREADY_EXISTS") == 1
    assert provider.calls == 1

    with SessionLocal() as db:
        assert db.scalar(
            select(func.count())
            .select_from(PaymentTransaction)
            .where(PaymentTransaction.order_id == order_id)
        ) == 1
        transaction = db.scalar(
            select(PaymentTransaction).where(PaymentTransaction.order_id == order_id)
        )
        assert transaction is not None
        assert transaction.status == "PENDING"
