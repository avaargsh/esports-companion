from decimal import Decimal

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
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def test_designated_offering_locks_price_and_assigns_provider_after_payment():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        customer = User(nickname="customer")
        player_user = User(nickname="player")
        game = Game(code="designated", name="Designated")
        db.add_all([customer, player_user, game])
        db.flush()

        sku = ServiceSKU(
            game_id=game.id,
            name="陪玩 1 小时",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        player = PlayerProfile(
            user_id=player_user.id,
            display_name="Selected Player",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        db.add_all([sku, player])
        db.flush()

        offering = ProviderOffering(
            player_id=player.id,
            sku_id=sku.id,
            price_override=2600,
            status="ACTIVE",
        )
        db.add(offering)
        db.commit()

        order = OrderService.create_order(
            db,
            user_id=customer.id,
            offering_id=offering.id,
            quantity=2,
        )
        assert order.designated_player_id == player.id
        assert order.unit_price == 2600
        assert order.total_amount == 5200
        assert order.status == "WAITING_PAYMENT"

        MockPaymentService.pay(db, order, "designated-payment")

        assert order.status == "ACCEPTED"
        assignment = db.scalar(
            select(OrderAssignment).where(OrderAssignment.order_id == order.id)
        )
        assert assignment is not None
        assert assignment.player_id == player.id
        assert assignment.assigned_by == "USER"
