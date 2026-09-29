from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.db import SessionLocal
from app.domain.order_state_machine import OrderStatus
from app.models import (
    Game,
    LedgerEntry,
    PlayerProfile,
    ServiceSKU,
    Settlement,
    User,
    Wallet,
)
from app.services.dispatch_service import DispatchService
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService
from app.services.settlement_service import SettlementService


def test_settlement_is_idempotent_and_writes_two_ledger_entries():
    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            platform = User(nickname=f"platform-{suffix}", role="PLATFORM")
            db.add(platform)

        customer = User(nickname=f"customer-{suffix}")
        player_user = User(nickname=f"player-user-{suffix}")
        game = Game(code=f"settle-{suffix}", name="Settlement Test")
        db.add_all([customer, player_user, game])
        db.flush()

        player = PlayerProfile(
            user_id=player_user.id,
            display_name="Settlement Player",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        sku = ServiceSKU(
            game_id=game.id,
            name="Settlement SKU",
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

        order = OrderService.create_order(db, user_id=customer.id, sku_id=sku.id)
        MockPaymentService.pay(db, order, f"pay-{suffix}")
        DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        DispatchService.start(db, order=order, player_id=player.id)
        DispatchService.finish(db, order=order, player_id=player.id)
        OrderService.transition(
            db,
            order,
            OrderStatus.COMPLETED,
            event_type="USER_CONFIRMED_FINISH",
            actor_type="USER",
            actor_id=str(customer.id),
        )

        first = SettlementService.settle(db, order)
        second = SettlementService.settle(db, order)

        assert first.id == second.id
        assert order.status == "SETTLED"
        assert db.scalar(
            select(func.count())
            .select_from(Settlement)
            .where(Settlement.order_id == order.id)
        ) == 1
        assert db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.biz_id == str(order.id))
        ) == 2

        player_wallet = db.scalar(select(Wallet).where(Wallet.user_id == player_user.id))
        assert player_wallet.available_balance == 2400
