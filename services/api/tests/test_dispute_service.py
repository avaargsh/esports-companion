from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import threading
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Dispute,
    Game,
    LedgerEntry,
    PlayerProfile,
    ProviderOffering,
    Refund,
    ServiceSKU,
    Settlement,
    User,
    Wallet,
)
from app.services.auto_confirm_service import AutoConfirmService
from app.services.dispatch_service import DispatchService
from app.services.dispute_service import DisputeService
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def _finish_requested_order():
    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            platform = User(nickname=f"platform-{suffix}", role="PLATFORM")
            db.add(platform)

        customer = User(nickname=f"dispute-customer-{suffix}")
        player_user = User(nickname=f"dispute-player-{suffix}")
        game = Game(code=f"dispute-{suffix}", name="Dispute")
        db.add_all([customer, player_user, game])
        db.flush()
        player = PlayerProfile(
            user_id=player_user.id,
            display_name="Dispute Player",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        sku = ServiceSKU(
            game_id=game.id,
            name="Dispute SKU",
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
        MockPaymentService.pay(db, order, f"dispute-pay-{suffix}")
        DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        DispatchService.start(db, order=order, player_id=player.id)
        DispatchService.finish(db, order=order, player_id=player.id)
        return order.id, customer.id, player_user.id, platform.id



def _accepted_order():
    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        customer = User(nickname=f"race-customer-{suffix}")
        player_user = User(nickname=f"race-player-{suffix}")
        game = Game(code=f"race-{suffix}", name="Dispatch Dispute Race")
        db.add_all([customer, player_user, game])
        db.flush()
        player = PlayerProfile(
            user_id=player_user.id,
            display_name="Race Player",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        sku = ServiceSKU(
            game_id=game.id,
            name="Race SKU",
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
        MockPaymentService.pay(db, order, f"race-pay-{suffix}")
        DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        return order.id, customer.id, player.id


def test_dispute_freezes_auto_confirm_and_is_idempotent():
    order_id, customer_id, _player_user_id, _platform_id = _finish_requested_order()
    key = f"dispute:{uuid4()}"

    with SessionLocal() as db:
        first = DisputeService.open(
            db,
            order_id=order_id,
            actor_user_id=customer_id,
            reason_code="SERVICE_QUALITY",
            description="not as expected",
            idempotency_key=key,
        )
        second = DisputeService.open(
            db,
            order_id=order_id,
            actor_user_id=customer_id,
            reason_code="SERVICE_QUALITY",
            description="not as expected",
            idempotency_key=key,
        )
        assert first.id == second.id
        assert first.status == "OPEN"
        assert first.held_amount == 3000
        assert OrderService.get(db, order_id).status == "DISPUTED"

    future = datetime.now(timezone.utc) + timedelta(
        seconds=settings.finish_confirm_timeout_seconds + 5
    )
    with SessionLocal() as db:
        processed = AutoConfirmService.process_due(
            db,
            now=future,
            timeout_seconds=settings.finish_confirm_timeout_seconds,
            limit=100,
        )
        assert order_id not in processed
        assert db.scalar(
            select(func.count())
            .select_from(Settlement)
            .where(Settlement.order_id == order_id)
        ) == 0


def test_platform_can_release_dispute_to_provider_and_settle():
    order_id, customer_id, player_user_id, platform_id = _finish_requested_order()

    with SessionLocal() as db:
        dispute = DisputeService.open(
            db,
            order_id=order_id,
            actor_user_id=customer_id,
            reason_code="SERVICE_QUALITY",
            description="review",
            idempotency_key=f"dispute:{uuid4()}",
        )
        resolved = DisputeService.release_to_provider(
            db,
            dispute_id=dispute.id,
            admin_user_id=platform_id,
        )
        assert resolved.status == "RESOLVED"
        assert resolved.resolution == "RELEASE_PROVIDER"
        assert OrderService.get(db, order_id).status == "SETTLED"
        assert db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.biz_id == str(order_id))
        ) == 2
        wallet = db.scalar(
            select(Wallet).where(Wallet.user_id == player_user_id)
        )
        assert wallet.available_balance == 2400


def test_platform_refund_resolution_never_credits_provider_wallet():
    order_id, customer_id, player_user_id, platform_id = _finish_requested_order()

    with SessionLocal() as db:
        dispute = DisputeService.open(
            db,
            order_id=order_id,
            actor_user_id=customer_id,
            reason_code="NOT_DELIVERED",
            description="refund",
            idempotency_key=f"dispute:{uuid4()}",
        )
        refund = DisputeService.approve_refund(
            db,
            dispute_id=dispute.id,
            admin_user_id=platform_id,
        )
        assert refund.status == "PENDING"
        assert refund.amount == 3000
        assert OrderService.get(db, order_id).status == "REFUNDING"

        completed = DisputeService.complete_refund(
            db,
            refund_id=refund.id,
            provider_refund_id="manual-refund-1",
            admin_user_id=platform_id,
        )
        assert completed.status == "COMPLETED"
        assert OrderService.get(db, order_id).status == "REFUNDED"

        dispute_row = db.get(Dispute, dispute.id)
        assert dispute_row.status == "RESOLVED"
        assert dispute_row.resolution == "REFUND_CUSTOMER"
        assert db.scalar(
            select(func.count())
            .select_from(Settlement)
            .where(Settlement.order_id == order_id)
        ) == 0
        wallet = db.scalar(
            select(Wallet).where(Wallet.user_id == player_user_id)
        )
        assert wallet is None or wallet.available_balance == 0
        assert db.scalar(
            select(func.count())
            .select_from(Refund)
            .where(Refund.order_id == order_id)
        ) == 1


def test_stale_start_cannot_overwrite_disputed_order():
    order_id, customer_id, player_id = _accepted_order()

    with SessionLocal() as stale_db:
        stale_order = OrderService.get(stale_db, order_id)

        with SessionLocal() as dispute_db:
            DisputeService.open(
                dispute_db,
                order_id=order_id,
                actor_user_id=customer_id,
                reason_code="SERVICE_QUALITY",
                description="race with start",
                idempotency_key=f"dispute:{uuid4()}",
            )

        with pytest.raises(ValueError, match="DISPUTED.*IN_SERVICE"):
            DispatchService.start(
                stale_db,
                order=stale_order,
                player_id=player_id,
            )
        stale_db.rollback()

    with SessionLocal() as db:
        assert OrderService.get(db, order_id).status == "DISPUTED"


def test_stale_finish_cannot_overwrite_disputed_order():
    order_id, customer_id, player_id = _accepted_order()

    with SessionLocal() as db:
        order = OrderService.get(db, order_id)
        DispatchService.start(db, order=order, player_id=player_id)

    with SessionLocal() as stale_db:
        stale_order = OrderService.get(stale_db, order_id)

        with SessionLocal() as dispute_db:
            DisputeService.open(
                dispute_db,
                order_id=order_id,
                actor_user_id=customer_id,
                reason_code="SERVICE_QUALITY",
                description="race with finish",
                idempotency_key=f"dispute:{uuid4()}",
            )

        with pytest.raises(ValueError, match="DISPUTED.*FINISH_REQUESTED"):
            DispatchService.finish(
                stale_db,
                order=stale_order,
                player_id=player_id,
            )
        stale_db.rollback()

    with SessionLocal() as db:
        assert OrderService.get(db, order_id).status == "DISPUTED"


def test_provider_refund_id_cannot_complete_two_refunds():
    first_order_id, first_customer_id, _first_player_user_id, platform_id = (
        _finish_requested_order()
    )
    second_order_id, second_customer_id, _second_player_user_id, _platform_id = (
        _finish_requested_order()
    )

    with SessionLocal() as db:
        first_dispute = DisputeService.open(
            db,
            order_id=first_order_id,
            actor_user_id=first_customer_id,
            reason_code="NOT_DELIVERED",
            description="first refund",
            idempotency_key=f"dispute:{uuid4()}",
        )
        first_refund = DisputeService.approve_refund(
            db,
            dispute_id=first_dispute.id,
            admin_user_id=platform_id,
        )

        second_dispute = DisputeService.open(
            db,
            order_id=second_order_id,
            actor_user_id=second_customer_id,
            reason_code="NOT_DELIVERED",
            description="second refund",
            idempotency_key=f"dispute:{uuid4()}",
        )
        second_refund = DisputeService.approve_refund(
            db,
            dispute_id=second_dispute.id,
            admin_user_id=platform_id,
        )

        DisputeService.complete_refund(
            db,
            refund_id=first_refund.id,
            provider_refund_id="manual:shared-refund-proof",
            admin_user_id=platform_id,
        )
        with pytest.raises(ValueError, match="REFUND_PROVIDER_ID_MISMATCH"):
            DisputeService.complete_refund(
                db,
                refund_id=first_refund.id,
                provider_refund_id="manual:different-proof",
                admin_user_id=platform_id,
            )

        with pytest.raises(ValueError, match="REFUND_PROVIDER_ID_REUSED"):
            DisputeService.complete_refund(
                db,
                refund_id=second_refund.id,
                provider_refund_id="manual:shared-refund-proof",
                admin_user_id=platform_id,
            )
        db.rollback()

        assert db.get(Refund, second_refund.id).status == "PENDING"
        assert OrderService.get(db, second_order_id).status == "REFUNDING"


def test_concurrent_dispute_open_replays_same_record():
    order_id, customer_id, _player_id = _accepted_order()
    idempotency_key = f"dispute:{uuid4()}"
    barrier = threading.Barrier(2)

    def open_once():
        with SessionLocal() as db:
            barrier.wait(timeout=5)
            dispute = DisputeService.open(
                db,
                order_id=order_id,
                actor_user_id=customer_id,
                reason_code="SERVICE_QUALITY",
                description="concurrent open",
                idempotency_key=idempotency_key,
            )
            return dispute.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = [
            future.result(timeout=10)
            for future in [pool.submit(open_once), pool.submit(open_once)]
        ]

    assert ids[0] == ids[1]
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(Dispute).where(
                    Dispute.idempotency_key == idempotency_key
                )
            )
        )
        assert len(rows) == 1
        assert OrderService.get(db, order_id).status == "DISPUTED"
