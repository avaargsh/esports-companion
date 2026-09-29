from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Game, OrderEvent, PaymentTransaction, ServiceSKU, User
from app.services.order_service import OrderService
from app.services.payment_service import MockPaymentService


def test_mock_payment_is_idempotent_and_enters_matching():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        user = User(nickname="customer")
        game = Game(code="wzry-test", name="王者荣耀")
        db.add_all([user, game])
        db.flush()
        sku = ServiceSKU(
            game_id=game.id,
            name="娱乐陪玩 1小时",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add(sku)
        db.commit()

        order = OrderService.create_order(db, user_id=user.id, sku_id=sku.id)
        MockPaymentService.pay(db, order, "pay-once")
        MockPaymentService.pay(db, order, "pay-once")

        assert order.status == "MATCHING"
        assert order.player_amount == 2400
        assert order.platform_fee == 600
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
        assert db.scalar(select(func.count()).select_from(OrderEvent)) == 3
