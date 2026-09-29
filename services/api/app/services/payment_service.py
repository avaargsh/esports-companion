from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, PaymentTransaction, User
from app.providers.payment import PaymentProvider
from app.services.order_service import OrderService


@dataclass(frozen=True)
class PaymentPreparation:
    order: Order
    transaction: PaymentTransaction
    client_payload: dict
    replayed: bool


class PaymentService:
    @staticmethod
    def prepare_payment(
        db: Session,
        *,
        order: Order,
        provider: PaymentProvider,
        idempotency_key: str,
    ) -> PaymentPreparation:
        existing = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.order_id != order.id:
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
            raw_payload = existing.raw_payload or {}
            return PaymentPreparation(
                order=order,
                transaction=existing,
                client_payload=raw_payload.get("clientPayload", {}),
                replayed=True,
            )

        if order.status != OrderStatus.WAITING_PAYMENT.value:
            raise ValueError("ORDER_NOT_WAITING_PAYMENT")

        payer = db.get(User, order.user_id)
        if not payer:
            raise ValueError("PAYMENT_PAYER_NOT_FOUND")

        intent = provider.create_payment(
            order=order,
            idempotency_key=idempotency_key,
            payer_subject=payer.openid,
        )
        if intent.provider.upper() != provider.name.upper():
            raise ValueError("PAYMENT_PROVIDER_MISMATCH")

        transaction = PaymentTransaction(
            order_id=order.id,
            provider=intent.provider.upper(),
            provider_txn_id=intent.provider_txn_id,
            idempotency_key=idempotency_key,
            amount=order.total_amount,
            status=intent.status,
            raw_payload={
                "provider": intent.raw_payload,
                "clientPayload": intent.client_payload,
            },
        )
        db.add(transaction)

        if intent.status == "SUCCESS":
            PaymentService._mark_paid(
                db,
                order,
                provider_name=intent.provider,
            )

        db.commit()
        db.refresh(transaction)
        return PaymentPreparation(
            order=order,
            transaction=transaction,
            client_payload=intent.client_payload,
            replayed=False,
        )

    @staticmethod
    def create_payment(
        db: Session,
        *,
        order: Order,
        provider: PaymentProvider,
        idempotency_key: str,
    ) -> Order:
        return PaymentService.prepare_payment(
            db,
            order=order,
            provider=provider,
            idempotency_key=idempotency_key,
        ).order

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
