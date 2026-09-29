from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import (
    Game,
    LedgerEntry,
    Order,
    OrderEvent,
    PlayerProfile,
    ProviderOffering,
    ServiceSKU,
    Settlement,
    User,
)
from app.services.auto_confirm_service import AutoConfirmService
from app.services.dispatch_service import DispatchService
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def _finish_requested_order():
    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            db.add(User(nickname=f"platform-{suffix}", role="PLATFORM"))

        customer = User(nickname=f"timeout-customer-{suffix}")
        player_user = User(nickname=f"timeout-player-user-{suffix}")
        game = Game(code=f"timeout-{suffix}", name="Timeout Test")
        db.add_all([customer, player_user, game])
        db.flush()

        player = PlayerProfile(
            user_id=player_user.id,
            display_name=f"Timeout Player {suffix}",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        sku = ServiceSKU(
            game_id=game.id,
            name="Timeout SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add_all([player, sku])
        db.flush()
        db.add(
            ProviderOffering(
                player_id=player.id,
                sku_id=sku.id,
                status="ACTIVE",
            )
        )
        db.commit()

        order = OrderService.create_order(
            db,
            user_id=customer.id,
            sku_id=sku.id,
        )
        MockPaymentService.pay(db, order, f"timeout-pay-{suffix}")
        DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        DispatchService.start(db, order=order, player_id=player.id)
        DispatchService.finish(db, order=order, player_id=player.id)
        return order.id


def test_due_finish_request_auto_confirms_and_settles_once():
    order_id = _finish_requested_order()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        order = db.get(Order, order_id)
        order.finish_requested_at = now - timedelta(minutes=31)
        db.commit()

    with SessionLocal() as db:
        assert AutoConfirmService.auto_confirm_one(
            db,
            order_id=order_id,
            now=now,
            timeout_seconds=1800,
        )

        order = db.get(Order, order_id)
        assert order.status == "SETTLED"
        assert db.scalar(
            select(func.count())
            .select_from(Settlement)
            .where(Settlement.order_id == order_id)
        ) == 1
        assert db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.biz_id == str(order_id))
        ) == 2
        assert db.scalar(
            select(func.count())
            .select_from(OrderEvent)
            .where(
                OrderEvent.order_id == order_id,
                OrderEvent.event_type == "AUTO_CONFIRM_FINISH",
            )
        ) == 1

        assert not AutoConfirmService.auto_confirm_one(
            db,
            order_id=order_id,
            now=now + timedelta(minutes=1),
            timeout_seconds=1800,
        )


def test_finish_request_before_deadline_is_not_auto_confirmed():
    order_id = _finish_requested_order()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        order = db.get(Order, order_id)
        order.finish_requested_at = now - timedelta(minutes=10)
        db.commit()

    with SessionLocal() as db:
        assert not AutoConfirmService.auto_confirm_one(
            db,
            order_id=order_id,
            now=now,
            timeout_seconds=1800,
        )
        order = db.get(Order, order_id)
        assert order.status == "FINISH_REQUESTED"
        assert db.scalar(
            select(func.count())
            .select_from(Settlement)
            .where(Settlement.order_id == order_id)
        ) == 0
