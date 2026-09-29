from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, PaymentTransaction, User
from app.providers.payment import PaymentProvider
from app.providers.payment_callback import VerifiedPaymentCallback
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
        # Serialize payment creation with cancellation and other payment attempts.
        # The checks below must happen after the row lock; otherwise two requests
        # with different idempotency keys can both observe "no pending payment"
        # and both create provider-side payment state.
        locked_order = db.scalar(
            select(Order).where(Order.id == order.id).with_for_update()
        )
        if not locked_order:
            raise ValueError("PAYMENT_ORDER_NOT_FOUND")
        order = locked_order

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

        existing_pending = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == provider.name.upper(),
                PaymentTransaction.status == "PENDING",
            )
        )
        if existing_pending:
            raise ValueError("PAYMENT_ATTEMPT_ALREADY_EXISTS")

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
    def apply_verified_success(
        db: Session,
        *,
        callback: VerifiedPaymentCallback,
    ) -> PaymentPreparation:
        order = db.scalar(
            select(Order)
            .where(Order.order_no == callback.out_trade_no)
            .with_for_update()
        )
        if not order:
            raise ValueError("PAYMENT_ORDER_NOT_FOUND")
        if order.total_amount != callback.amount:
            raise ValueError("PAYMENT_AMOUNT_MISMATCH")
        if callback.currency.upper() != "CNY":
            raise ValueError("PAYMENT_CURRENCY_MISMATCH")

        payer = db.get(User, order.user_id)
        if not payer or not payer.openid:
            raise ValueError("PAYMENT_PAYER_NOT_FOUND")
        if callback.payer_subject != payer.openid:
            raise ValueError("PAYMENT_PAYER_MISMATCH")

        existing_success = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider == callback.provider.upper(),
                PaymentTransaction.provider_txn_id == callback.provider_txn_id,
            )
        )
        if existing_success:
            if existing_success.order_id != order.id:
                raise ValueError("PAYMENT_PROVIDER_TXN_REUSED")
            if existing_success.amount != callback.amount:
                raise ValueError("PAYMENT_AMOUNT_MISMATCH")
            return PaymentPreparation(
                order=order,
                transaction=existing_success,
                client_payload=(existing_success.raw_payload or {}).get(
                    "clientPayload", {}
                ),
                replayed=True,
            )

        pending = db.scalar(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == callback.provider.upper(),
                PaymentTransaction.status == "PENDING",
            )
            .order_by(PaymentTransaction.created_at.desc())
            .with_for_update()
        )
        if not pending:
            raise ValueError("PAYMENT_PENDING_TRANSACTION_NOT_FOUND")
        if pending.amount != callback.amount:
            raise ValueError("PAYMENT_AMOUNT_MISMATCH")

        pending.provider_txn_id = callback.provider_txn_id
        pending.status = "SUCCESS"
        previous_payload = pending.raw_payload or {}
        pending.raw_payload = {
            **previous_payload,
            "callback": callback.raw_event,
            "verifiedResource": callback.resource,
        }

        if order.status == OrderStatus.WAITING_PAYMENT.value:
            PaymentService._mark_paid(
                db,
                order,
                provider_name=callback.provider,
            )
        elif order.status not in {
            OrderStatus.PAID.value,
            OrderStatus.MATCHING.value,
            OrderStatus.ACCEPTED.value,
            OrderStatus.IN_SERVICE.value,
            OrderStatus.FINISH_REQUESTED.value,
            OrderStatus.COMPLETED.value,
            OrderStatus.SETTLED.value,
        }:
            raise ValueError(f"ORDER_NOT_PAYABLE:{order.status}")

        db.commit()
        db.refresh(pending)
        return PaymentPreparation(
            order=order,
            transaction=pending,
            client_payload=(pending.raw_payload or {}).get("clientPayload", {}),
            replayed=False,
        )

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
        if order.designated_player_id:
            from app.services.dispatch_service import DispatchService

            DispatchService.assign_designated(db, order=order)


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
