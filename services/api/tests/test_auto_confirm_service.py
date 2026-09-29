from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Game,
    LedgerEntry,
    OrderEvent,
    PlayerProfile,
    ProviderOffering,
    ServiceSKU,
    Settlement,
    User,
    Wallet,
)
from app.services.auto_confirm_service import AutoConfirmService
from app.services.completion_service import CompletionService
from app.services.dispatch_service import DispatchService
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def _finish_requested_order():
    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            platform = User(nickname=f"platform-{suffix}", role="PLATFORM")
            db.add(platform)

        customer = User(nickname=f"auto-customer-{suffix}")
        player_user = User(nickname=f"auto-player-{suffix}")
        game = Game(code=f"auto-{suffix}", name="Auto Confirm")
        db.add_all([customer, player_user, game])
        db.flush()

        player = PlayerProfile(
            user_id=player_user.id,
            display_name="Auto Player",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        sku = ServiceSKU(
            game_id=game.id,
            name="Auto Confirm SKU",
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
        MockPaymentService.pay(db, order, f"auto-pay-{suffix}")
        DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        DispatchService.start(db, order=order, player_id=player.id)
        DispatchService.finish(db, order=order, player_id=player.id)
        return order.id, customer.id, player_user.id


def test_auto_confirm_settles_due_order_once():
    order_id, _customer_id, player_user_id = _finish_requested_order()
    due_now = datetime.now(timezone.utc) + timedelta(
        seconds=settings.finish_confirm_timeout_seconds + 5
    )

    with SessionLocal() as db:
        processed = AutoConfirmService.process_due(
            db,
            now=due_now,
            timeout_seconds=settings.finish_confirm_timeout_seconds,
            limit=10,
        )
        assert order_id in processed

    with SessionLocal() as db:
        order = OrderService.get(db, order_id)
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
        event = db.scalar(
            select(OrderEvent).where(
                OrderEvent.order_id == order_id,
                OrderEvent.event_type == "AUTO_CONFIRM_FINISH",
            )
        )
        assert event is not None
        wallet = db.scalar(
            select(Wallet).where(Wallet.user_id == player_user_id)
        )
        assert wallet.available_balance == 2400

    with SessionLocal() as db:
        processed = AutoConfirmService.process_due(
            db,
            now=due_now,
            timeout_seconds=settings.finish_confirm_timeout_seconds,
            limit=10,
        )
        assert order_id not in processed


def test_auto_confirm_ignores_order_before_deadline():
    order_id, _customer_id, _player_user_id = _finish_requested_order()

    with SessionLocal() as db:
        order = OrderService.get(db, order_id)
        before_due = order.finish_requested_at + timedelta(
            seconds=settings.finish_confirm_timeout_seconds - 1
        )
        processed = AutoConfirmService.process_due(
            db,
            now=before_due,
            timeout_seconds=settings.finish_confirm_timeout_seconds,
            limit=10,
        )
        assert order_id not in processed
        db.refresh(order)
        assert order.status == "FINISH_REQUESTED"


def test_manual_confirm_prevents_later_auto_confirm():
    order_id, customer_id, _player_user_id = _finish_requested_order()

    with SessionLocal() as db:
        confirmed = CompletionService.confirm_by_user(
            db,
            order_id=order_id,
            user_id=customer_id,
        )
        assert confirmed.status == "SETTLED"

    due_now = datetime.now(timezone.utc) + timedelta(
        seconds=settings.finish_confirm_timeout_seconds + 5
    )
    with SessionLocal() as db:
        assert AutoConfirmService.process_due(
            db,
            now=due_now,
            timeout_seconds=settings.finish_confirm_timeout_seconds,
            limit=10,
        ) == []
        assert db.scalar(
            select(func.count())
            .select_from(Settlement)
            .where(Settlement.order_id == order_id)
        ) == 1
