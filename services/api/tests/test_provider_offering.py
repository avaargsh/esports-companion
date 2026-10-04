from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Game, PlayerProfile, PlayerSkill, ProviderOffering, ServiceSKU, User
from app.services.dispatch_service import DispatchService, PlayerNotEligible
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def _fixture():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()

    customer = User(nickname="offering-customer")
    player_user = User(nickname="offering-player")
    game = Game(code="offering-game", name="Offering Game")
    db.add_all([customer, player_user, game])
    db.flush()

    sku = ServiceSKU(
        game_id=game.id,
        name="Offering SKU",
        service_type="ENTERTAINMENT",
        duration_minutes=60,
        price=3000,
        platform_fee_rate=Decimal("0.2000"),
    )
    player = PlayerProfile(
        user_id=player_user.id,
        display_name="Offering Player",
        verification_status="APPROVED",
        service_status="AVAILABLE",
    )
    db.add_all([sku, player])
    db.commit()

    order = OrderService.create_order(
        db,
        user_id=customer.id,
        sku_id=sku.id,
    )
    MockPaymentService.pay(db, order, "offering-payment")
    return db, order, player, sku


def test_player_cannot_claim_without_active_offering():
    db, order, player, _sku = _fixture()
    try:
        with pytest.raises(PlayerNotEligible, match="PLAYER_NOT_OFFERING_SKU"):
            DispatchService.claim(
                db,
                order_id=order.id,
                player_id=player.id,
                expected_version=order.version,
            )
    finally:
        db.close()


def test_active_offering_allows_claim():
    db, order, player, sku = _fixture()
    try:
        db.add_all([
            PlayerSkill(
                player_id=player.id,
                game_id=sku.game_id,
                rank="已认证",
                description="测试技能",
                evidence_url="https://example.com/proof.png",
                verification_status="APPROVED",
                status="ACTIVE",
            ),
            ProviderOffering(
                player_id=player.id,
                sku_id=sku.id,
                status="ACTIVE",
            ),
        ])
        db.commit()

        claimed = DispatchService.claim(
            db,
            order_id=order.id,
            player_id=player.id,
            expected_version=order.version,
        )
        assert claimed.status == "ACCEPTED"
    finally:
        db.close()


def test_inactive_offering_does_not_allow_claim():
    db, order, player, sku = _fixture()
    try:
        db.add(
            ProviderOffering(
                player_id=player.id,
                sku_id=sku.id,
                status="INACTIVE",
            )
        )
        db.commit()

        with pytest.raises(PlayerNotEligible, match="PLAYER_NOT_OFFERING_SKU"):
            DispatchService.claim(
                db,
                order_id=order.id,
                player_id=player.id,
                expected_version=order.version,
            )
    finally:
        db.close()
