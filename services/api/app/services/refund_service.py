import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, PaymentTransaction, Refund
from app.providers.refund import RefundProvider
from app.providers.refund_callback import VerifiedRefundCallback
from app.services.dispute_service import DisputeService


class RefundService:
    @staticmethod
    def submit(
        db: Session,
        *,
        refund_id: uuid.UUID,
        provider: RefundProvider,
        actor_user_id: uuid.UUID | None = None,
    ) -> Refund:
        refund = db.scalar(select(Refund).where(Refund.id == refund_id).with_for_update())
        if not refund:
            raise LookupError("REFUND_NOT_FOUND")
        if refund.status == "COMPLETED":
            return refund
        if refund.status in {"PROCESSING", "CLOSED", "ABNORMAL"}:
            return refund
        if refund.status not in {"PENDING", "SUBMITTING"}:
            raise ValueError("REFUND_NOT_SUBMITTABLE")

        order = db.scalar(select(Order).where(Order.id == refund.order_id).with_for_update())
        if not order or order.status != OrderStatus.REFUNDING.value:
            raise ValueError("ORDER_NOT_REFUNDING")

        payment = db.scalar(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status == "SUCCESS",
            )
            .order_by(PaymentTransaction.created_at.desc())
        )
        if not payment:
            raise ValueError("SUCCESSFUL_PAYMENT_NOT_FOUND")

        if not refund.out_refund_no:
            refund.out_refund_no = f"RFD_{refund.id.hex}"
        refund.provider = provider.name.upper()
        refund.status = "SUBMITTING"
        db.commit()

        intent = provider.create_refund(
            refund=refund,
            order=order,
            payment=payment,
            reason="Dispute refund",
        )

        refund = db.scalar(select(Refund).where(Refund.id == refund_id).with_for_update())
        if not refund:
            raise LookupError("REFUND_NOT_FOUND")
        if intent.provider.upper() != provider.name.upper():
            raise ValueError("REFUND_PROVIDER_MISMATCH")

        refund.provider = intent.provider.upper()
        refund.provider_refund_id = intent.provider_refund_id
        refund.raw_payload = {**(refund.raw_payload or {}), "submit": intent.raw_payload}

        if intent.status == "SUCCESS":
            return DisputeService.complete_refund(
                db,
                refund_id=refund.id,
                provider_refund_id=intent.provider_refund_id or "",
                admin_user_id=actor_user_id,
            )

        refund.status = intent.status
        if intent.status in {"CLOSED", "ABNORMAL"}:
            refund.failure_reason = f"PROVIDER_REFUND_{intent.status}"
        db.commit()
        db.refresh(refund)
        return refund

    @staticmethod
    def apply_wechat_callback(
        db: Session,
        *,
        callback: VerifiedRefundCallback,
    ) -> Refund:
        refund = db.scalar(
            select(Refund)
            .where(Refund.out_refund_no == callback.out_refund_no)
            .with_for_update()
        )
        if not refund:
            raise ValueError("REFUND_NOT_FOUND")
        if refund.provider not in {"WECHAT", "MANUAL"}:
            raise ValueError("REFUND_PROVIDER_MISMATCH")

        order = db.scalar(select(Order).where(Order.id == refund.order_id).with_for_update())
        if not order:
            raise ValueError("REFUND_ORDER_NOT_FOUND")
        if order.order_no != callback.out_trade_no:
            raise ValueError("REFUND_ORDER_NO_MISMATCH")
        if callback.total_amount != order.total_amount:
            raise ValueError("REFUND_TOTAL_AMOUNT_MISMATCH")
        if callback.refund_amount != refund.amount:
            raise ValueError("REFUND_AMOUNT_MISMATCH")

        payment = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "WECHAT",
                PaymentTransaction.status == "SUCCESS",
            )
        )
        if not payment or payment.provider_txn_id != callback.provider_txn_id:
            raise ValueError("REFUND_PAYMENT_TRANSACTION_MISMATCH")
        if refund.provider_refund_id and refund.provider_refund_id != callback.provider_refund_id:
            raise ValueError("REFUND_PROVIDER_ID_MISMATCH")

        refund.provider = "WECHAT"
        refund.provider_refund_id = callback.provider_refund_id
        refund.raw_payload = {
            **(refund.raw_payload or {}),
            "callback": callback.raw_event,
            "verifiedResource": callback.resource,
        }

        if callback.refund_status == "SUCCESS":
            if refund.status == "COMPLETED":
                return refund
            return DisputeService.complete_refund(
                db,
                refund_id=refund.id,
                provider_refund_id=callback.provider_refund_id,
                admin_user_id=None,
            )

        refund.status = callback.refund_status
        refund.failure_reason = f"PROVIDER_REFUND_{callback.refund_status}"
        db.commit()
        db.refresh(refund)
        return refund
