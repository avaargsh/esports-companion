import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Game, OrderAssignment, PlayerProfile, ServiceSKU, User
from app.services.dispatch_service import DispatchService, OrderAlreadyClaimed
from app.services.order_service import MockPaymentService, OrderService


def _claim(order_id, player_id, expected_version):
    with SessionLocal() as db:
        try:
            DispatchService.claim(
                db,
                order_id=order_id,
                player_id=player_id,
                expected_version=expected_version,
            )
            return "success"
        except OrderAlreadyClaimed:
            return "conflict"


def test_one_winner_under_100_concurrent_claims():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        customer = User(nickname=f"claim-customer-{suffix}")
        game = Game(code=f"claim-{suffix}", name="Claim Test")
        db.add_all([customer, game])
        db.flush()
        sku = ServiceSKU(
            game_id=game.id,
            name="Concurrent Claim SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add(sku)

        player_ids = []
        for index in range(100):
            user = User(nickname=f"player-{suffix}-{index}")
            db.add(user)
            db.flush()
            player = PlayerProfile(
                user_id=user.id,
                display_name=f"Player {index}",
                verification_status="APPROVED",
                service_status="AVAILABLE",
            )
            db.add(player)
            db.flush()
            player_ids.append(player.id)
        db.commit()

        order = OrderService.create_order(db, user_id=customer.id, sku_id=sku.id)
        MockPaymentService.pay(db, order, f"claim-payment-{suffix}")
        expected_version = order.version
        order_id = order.id

    async def run():
        return await asyncio.gather(
            *[
                asyncio.to_thread(_claim, order_id, player_id, expected_version)
                for player_id in player_ids
            ]
        )

    results = asyncio.run(run())

    assert results.count("success") == 1
    assert results.count("conflict") == 99

    with SessionLocal() as db:
        active_count = db.scalar(
            select(func.count())
            .select_from(OrderAssignment)
            .where(
                OrderAssignment.order_id == order_id,
                OrderAssignment.status == "ACTIVE",
            )
        )
        assert active_count == 1
