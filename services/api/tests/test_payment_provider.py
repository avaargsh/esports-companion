from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Game, PaymentTransaction, ServiceSKU, User
from app.providers.payment import MockPaymentProvider
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService


def test_mock_provider_is_adapter_and_payment_core_stays_idempotent():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        customer = User(nickname="adapter-customer")
        game = Game(code="adapter-game", name="Adapter Test")
        db.add_all([customer, game])
        db.flush()

        sku = ServiceSKU(
            game_id=game.id,
            name="Adapter SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add(sku)
        db.commit()

        order = OrderService.create_order(
            db,
            user_id=customer.id,
            sku_id=sku.id,
        )
        provider = MockPaymentProvider()

        PaymentService.create_payment(
            db,
            order=order,
            provider=provider,
            idempotency_key="adapter-pay-once",
        )
        PaymentService.create_payment(
            db,
            order=order,
            provider=provider,
            idempotency_key="adapter-pay-once",
        )

        assert order.status == "MATCHING"
        assert db.scalar(
            select(func.count()).select_from(PaymentTransaction)
        ) == 1
        tx = db.scalar(select(PaymentTransaction))
        assert tx.provider == "MOCK"
        assert tx.status == "SUCCESS"
