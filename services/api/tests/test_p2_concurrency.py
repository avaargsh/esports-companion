import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy import func, select

from app.db import SessionLocal
from app.domain.order_state_machine import OrderStatus
from app.models import (
    Dispute,
    Game,
    LedgerEntry,
    OrderMessage,
    OutboxEvent,
    PlayerProfile,
    ProviderOffering,
    ServiceSKU,
    Settlement,
    User,
    Wallet,
)
from app.services.dispatch_service import DispatchService
from app.services.dispute_service import DisputeService
from app.services.order_messaging_service import OrderMessagingService
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService
from app.services.settlement_service import SettlementService


def _accepted_order():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            platform = User(nickname=f"platform-{suffix}", role="PLATFORM")
            db.add(platform)
        customer = User(nickname=f"p2-customer-{suffix}")
        player_user = User(nickname=f"p2-player-{suffix}", role="PLAYER")
        game = Game(code=f"p2-{suffix}", name="P2 Concurrency")
        db.add_all([customer, player_user, game])
        db.flush()
        player = PlayerProfile(
            user_id=player_user.id,
            display_name="P2 Player",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        sku = ServiceSKU(
            game_id=game.id,
            name="P2 SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add_all([player, sku])
        db.flush()
        db.add(ProviderOffering(player_id=player.id, sku_id=sku.id, status="ACTIVE"))
        db.commit()
        order = OrderService.create_order(db, user_id=customer.id, sku_id=sku.id)
        MockPaymentService.pay(db, order, f"p2-pay-{suffix}")
        DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        return order.id, customer.id, player_user.id, player.id


def test_concurrent_dispute_open_same_key_returns_one_dispute():
    order_id, customer_id, _player_user_id, _player_id = _accepted_order()
    key = f"p2-dispute-{uuid.uuid4()}"
    barrier = threading.Barrier(2)

    def open_dispute():
        with SessionLocal() as db:
            barrier.wait(timeout=5)
            result = DisputeService.open(
                db,
                order_id=order_id,
                actor_user_id=customer_id,
                reason_code="SERVICE_QUALITY",
                description="same request",
                idempotency_key=key,
            )
            return result.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = [future.result(timeout=10) for future in [
            pool.submit(open_dispute),
            pool.submit(open_dispute),
        ]]

    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(Dispute).where(Dispute.order_id == order_id)
        ) == 1
        assert OrderService.get(db, order_id).status == "DISPUTED"


def test_concurrent_message_replay_creates_one_message_and_one_outbox_event():
    order_id, customer_id, _player_user_id, _player_id = _accepted_order()
    client_message_id = f"p2-message-{uuid.uuid4()}"
    barrier = threading.Barrier(2)

    def send():
        with SessionLocal() as db:
            order = OrderService.get(db, order_id)
            barrier.wait(timeout=5)
            message = OrderMessagingService.create_message(
                db,
                order=order,
                user_id=customer_id,
                roles=("USER",),
                client_message_id=client_message_id,
                content="same message",
            )
            return message.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = [future.result(timeout=10) for future in [
            pool.submit(send),
            pool.submit(send),
        ]]

    assert ids[0] == ids[1]
    with SessionLocal() as db:
        messages = list(db.scalars(select(OrderMessage).where(
            OrderMessage.order_id == order_id,
            OrderMessage.client_message_id == client_message_id,
        )))
        assert len(messages) == 1
        assert db.scalar(
            select(func.count()).select_from(OutboxEvent).where(
                OutboxEvent.event_type == "ORDER_MESSAGE_CREATED",
                OutboxEvent.payload_json["messageId"].as_string() == str(messages[0].id),
            )
        ) == 1


def test_concurrent_settlement_credits_wallets_once():
    order_id, customer_id, player_user_id, player_id = _accepted_order()
    with SessionLocal() as db:
        order = OrderService.get(db, order_id)
        DispatchService.start(db, order=order, player_id=player_id)
        DispatchService.finish(db, order=order, player_id=player_id)
        OrderService.transition(
            db,
            order,
            OrderStatus.COMPLETED,
            event_type="P2_TEST_COMPLETED",
            actor_type="USER",
            actor_id=str(customer_id),
        )
        db.commit()

    barrier = threading.Barrier(2)

    def settle():
        with SessionLocal() as db:
            order = OrderService.get(db, order_id)
            barrier.wait(timeout=5)
            result = SettlementService.settle(db, order)
            return result.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = [future.result(timeout=10) for future in [
            pool.submit(settle),
            pool.submit(settle),
        ]]

    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(Settlement).where(Settlement.order_id == order_id)
        ) == 1
        assert db.scalar(
            select(func.count()).select_from(LedgerEntry).where(
                LedgerEntry.biz_type == "ORDER_SETTLEMENT",
                LedgerEntry.biz_id == str(order_id),
            )
        ) == 2
        player_wallet = db.scalar(select(Wallet).where(Wallet.user_id == player_user_id))
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        platform_wallet = db.scalar(select(Wallet).where(Wallet.user_id == platform.id))
        assert player_wallet.available_balance == 2400
        assert platform_wallet.available_balance == 600
        assert OrderService.get(db, order_id).status == "SETTLED"
