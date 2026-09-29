from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, PaymentTransaction
from app.providers.payment import PaymentProvider
from app.services.order_service import OrderService


class PaymentService:
    @staticmethod
    def create_payment(
        db: Session,
        *,
        order: Order,
        provider: PaymentProvider,
        idempotency_key: str,
    ) -> Order:
        existing = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.order_id != order.id:
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
            return order

        if order.status != OrderStatus.WAITING_PAYMENT.value:
            raise ValueError("ORDER_NOT_WAITING_PAYMENT")

        intent = provider.create_payment(
            order=order,
            idempotency_key=idempotency_key,
        )
        if intent.provider.upper() != provider.name.upper():
            raise ValueError("PAYMENT_PROVIDER_MISMATCH")

        db.add(
            PaymentTransaction(
                order_id=order.id,
                provider=intent.provider.upper(),
                provider_txn_id=intent.provider_txn_id,
                idempotency_key=idempotency_key,
                amount=order.total_amount,
                status=intent.status,
                raw_payload=intent.raw_payload,
            )
        )

        if intent.status == "SUCCESS":
            PaymentService._mark_paid(db, order, provider_name=intent.provider)

        db.commit()
        return order

    @staticmethod
    def _mark_paid(
        db: Session,
        order: Order,
        *,
        provider_name: str,
    ) -> None:
        OrderService.transition(
            db,
            order,
            OrderStatus.PAID,
            event_type="PAYMENT_SUCCESS",
            actor_type="PAYMENT",
            payload={"provider": provider_name.upper()},
        )
        OrderService.transition(
            db,
            order,
            OrderStatus.MATCHING,
            event_type="ORDER_ENTERED_MATCHING",
            actor_type="SYSTEM",
        )


class MockPaymentService:
    """Compatibility facade for the v0.1 /mock-pay API and existing tests."""

    @staticmethod
    def pay(db: Session, order: Order, idempotency_key: str) -> Order:
        from app.providers.payment import MockPaymentProvider

        return PaymentService.create_payment(
            db,
            order=order,
            provider=MockPaymentProvider(),
            idempotency_key=idempotency_key,
        )
