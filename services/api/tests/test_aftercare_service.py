from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    Game,
    OrderAssignment,
    PlayerProfile,
    ProviderOffering,
    ServiceSKU,
    User,
)
from app.services.aftercare_service import AftercareService
from app.services.dispute_service import DisputeService
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def _order(*, designated: bool):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()

    customer = User(nickname="aftercare-customer")
    platform = User(nickname="aftercare-platform", role="PLATFORM")
    player_user = User(nickname="aftercare-player")
    game = Game(code="aftercare", name="Aftercare")
    db.add_all([customer, platform, player_user, game])
    db.flush()

    sku = ServiceSKU(
        game_id=game.id,
        name="Aftercare SKU",
        service_type="ENTERTAINMENT",
        duration_minutes=60,
        price=3000,
        platform_fee_rate=Decimal("0.2000"),
    )
    player = PlayerProfile(
        user_id=player_user.id,
        display_name="Aftercare Player",
        verification_status="APPROVED",
        service_status="AVAILABLE",
    )
    db.add_all([sku, player])
    db.flush()

    offering = ProviderOffering(
        player_id=player.id,
        sku_id=sku.id,
        status="ACTIVE",
    )
    db.add(offering)
    db.commit()

    if designated:
        order = OrderService.create_order(
            db,
            user_id=customer.id,
            offering_id=offering.id,
        )
    else:
        order = OrderService.create_order(
            db,
            user_id=customer.id,
            sku_id=sku.id,
        )
    MockPaymentService.pay(db, order, f"aftercare-pay-{designated}")
    return db, customer, platform, player, order


def test_assignment_timeout_requeues_and_clears_designation():
    db, _customer, _platform, player, order = _order(designated=True)
    try:
        assert order.status == "ACCEPTED"
        now = datetime.now(timezone.utc)
        order.accepted_at = now - timedelta(minutes=20)
        db.commit()

        changed = AftercareService.requeue_one(
            db,
            order_id=order.id,
            now=now,
            timeout_seconds=600,
        )

        assert changed is True
        assert order.status == "MATCHING"
        assert order.designated_player_id is None
        assignment = db.scalar(
            select(OrderAssignment).where(
                OrderAssignment.order_id == order.id,
                OrderAssignment.player_id == player.id,
            )
        )
        assert assignment.status == "RELEASED"
        assert assignment.released_at is not None
    finally:
        db.close()


def test_fresh_assignment_is_not_requeued():
    db, _customer, _platform, _player, order = _order(designated=True)
    try:
        now = datetime.now(timezone.utc)
        order.accepted_at = now - timedelta(minutes=2)
        db.commit()

        changed = AftercareService.requeue_one(
            db,
            order_id=order.id,
            now=now,
            timeout_seconds=600,
        )
        assert changed is False
        assert order.status == "ACCEPTED"
    finally:
        db.close()


def test_matching_refund_request_uses_dispute_and_cannot_release_provider():
    db, customer, platform, _player, order = _order(designated=False)
    try:
        assert order.status == "MATCHING"
        dispute = DisputeService.open(
            db,
            order_id=order.id,
            actor_user_id=customer.id,
            reason_code="CANCEL_BEFORE_SERVICE",
            description="no longer needed",
            idempotency_key=f"refund-request:{order.id}",
        )
        assert order.status == "DISPUTED"
        assert dispute.held_amount == order.total_amount

        with pytest.raises(ValueError, match="DISPUTE_HAS_NO_PROVIDER_TO_RELEASE"):
            DisputeService.release_to_provider(
                db,
                dispute_id=dispute.id,
                admin_user_id=platform.id,
            )
        db.rollback()

        refund = DisputeService.approve_refund(
            db,
            dispute_id=dispute.id,
            admin_user_id=platform.id,
        )
        assert refund.status == "PENDING"
        assert order.status == "REFUNDING"
    finally:
        db.close()


def test_refund_approval_releases_active_assignment():
    db, customer, platform, player, order = _order(designated=True)
    try:
        assert order.status == "ACCEPTED"
        dispute = DisputeService.open(
            db,
            order_id=order.id,
            actor_user_id=customer.id,
            reason_code="CANCEL_BEFORE_SERVICE",
            description="provider did not start",
            idempotency_key=f"refund-request:{order.id}",
        )
        refund = DisputeService.approve_refund(
            db,
            dispute_id=dispute.id,
            admin_user_id=platform.id,
        )
        assert refund.status == "PENDING"
        assert order.status == "REFUNDING"

        assignment = db.scalar(
            select(OrderAssignment).where(
                OrderAssignment.order_id == order.id,
                OrderAssignment.player_id == player.id,
            )
        )
        assert assignment.status == "RELEASED"
        assert assignment.released_at is not None
    finally:
        db.close()
