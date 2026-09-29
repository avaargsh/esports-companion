import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import (
    Dispute,
    Order,
    OrderAssignment,
    PlayerProfile,
    Refund,
)
from app.services.order_service import OrderNotFound, OrderService
from app.services.settlement_service import SettlementService


class DisputeService:
    OPENABLE_STATUSES = {
        OrderStatus.MATCHING.value,
        OrderStatus.ACCEPTED.value,
        OrderStatus.IN_SERVICE.value,
        OrderStatus.FINISH_REQUESTED.value,
    }

    @staticmethod
    def open(
        db: Session,
        *,
        order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        reason_code: str,
        description: str,
        idempotency_key: str,
    ) -> Dispute:
        existing = db.scalar(
            select(Dispute).where(Dispute.idempotency_key == idempotency_key)
        )
        if existing:
            if existing.order_id != order_id or existing.opened_by_user_id != actor_user_id:
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
            return existing

        order = db.scalar(
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not order:
            raise OrderNotFound(str(order_id))

        # The first lookup can race with another request using the same
        # idempotency key. Re-check only after the order serialization point.
        existing = db.scalar(
            select(Dispute).where(Dispute.idempotency_key == idempotency_key)
        )
        if existing:
            if existing.order_id != order_id or existing.opened_by_user_id != actor_user_id:
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
            return existing

        if order.status not in DisputeService.OPENABLE_STATUSES:
            raise ValueError("ORDER_NOT_DISPUTABLE")

        actor_role = DisputeService._actor_role(
            db,
            order=order,
            actor_user_id=actor_user_id,
        )
        dispute = Dispute(
            order_id=order.id,
            status="OPEN",
            opened_by_user_id=actor_user_id,
            opened_by_role=actor_role,
            reason_code=reason_code.upper(),
            description=description,
            held_amount=order.total_amount,
            idempotency_key=idempotency_key,
        )
        db.add(dispute)
        db.flush()

        OrderService.transition(
            db,
            order,
            OrderStatus.DISPUTED,
            event_type="DISPUTE_OPENED",
            actor_type=actor_role,
            actor_id=str(actor_user_id),
            payload={
                "disputeId": str(dispute.id),
                "reasonCode": dispute.reason_code,
                "heldAmount": dispute.held_amount,
            },
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(Dispute).where(
                    Dispute.idempotency_key == idempotency_key
                )
            )
            if existing:
                if (
                    existing.order_id != order_id
                    or existing.opened_by_user_id != actor_user_id
                ):
                    raise ValueError("IDEMPOTENCY_KEY_REUSED")
                return existing
            raise
        db.refresh(dispute)
        return dispute

    @staticmethod
    def release_to_provider(
        db: Session,
        *,
        dispute_id: uuid.UUID,
        admin_user_id: uuid.UUID,
    ) -> Dispute:
        dispute, order = DisputeService._locked_open_dispute(db, dispute_id)
        if dispute.status == "RESOLVED" and dispute.resolution == "RELEASE_PROVIDER":
            return dispute

        active_assignment = db.scalar(
            select(OrderAssignment).where(
                OrderAssignment.order_id == order.id,
                OrderAssignment.status == "ACTIVE",
            )
        )
        if not active_assignment:
            raise ValueError("DISPUTE_HAS_NO_PROVIDER_TO_RELEASE")

        dispute.status = "RESOLVED"
        dispute.resolution = "RELEASE_PROVIDER"
        dispute.resolved_by_user_id = admin_user_id
        dispute.resolved_at = datetime.now(timezone.utc)

        OrderService.transition(
            db,
            order,
            OrderStatus.COMPLETED,
            event_type="DISPUTE_RELEASED_TO_PROVIDER",
            actor_type="PLATFORM",
            actor_id=str(admin_user_id),
            payload={"disputeId": str(dispute.id)},
        )
        SettlementService.settle(db, order)
        db.refresh(dispute)
        return dispute

    @staticmethod
    def approve_refund(
        db: Session,
        *,
        dispute_id: uuid.UUID,
        admin_user_id: uuid.UUID,
    ) -> Refund:
        dispute = db.scalar(
            select(Dispute)
            .where(Dispute.id == dispute_id)
            .with_for_update()
        )
        if not dispute:
            raise LookupError("DISPUTE_NOT_FOUND")

        existing = db.scalar(select(Refund).where(Refund.dispute_id == dispute.id))
        if existing:
            return existing
        if dispute.status != "OPEN":
            raise ValueError("DISPUTE_NOT_OPEN")

        order = db.scalar(
            select(Order)
            .where(Order.id == dispute.order_id)
            .with_for_update()
        )
        if not order or order.status != OrderStatus.DISPUTED.value:
            raise ValueError("ORDER_NOT_DISPUTED")

        assignment = db.scalar(
            select(OrderAssignment)
            .where(
                OrderAssignment.order_id == order.id,
                OrderAssignment.status == "ACTIVE",
            )
            .with_for_update()
        )
        if assignment:
            assignment.status = "RELEASED"
            assignment.released_at = datetime.now(timezone.utc)

        refund = Refund(
            order_id=order.id,
            dispute_id=dispute.id,
            amount=order.total_amount,
            status="PENDING",
            provider="MANUAL",
            out_refund_no=f"RFD_{uuid.uuid4().hex}",
            idempotency_key=f"order:{order.id}:refund",
            raw_payload={},
        )
        db.add(refund)
        dispute.status = "RESOLVING"
        dispute.resolution = "REFUND_CUSTOMER"
        dispute.resolved_by_user_id = admin_user_id

        OrderService.transition(
            db,
            order,
            OrderStatus.REFUNDING,
            event_type="DISPUTE_REFUND_APPROVED",
            actor_type="PLATFORM",
            actor_id=str(admin_user_id),
            payload={
                "disputeId": str(dispute.id),
                "refundId": str(refund.id),
                "amount": refund.amount,
            },
        )
        db.commit()
        db.refresh(refund)
        return refund

    @staticmethod
    def complete_refund(
        db: Session,
        *,
        refund_id: uuid.UUID,
        provider_refund_id: str,
        admin_user_id: uuid.UUID | None,
    ) -> Refund:
        refund = db.scalar(
            select(Refund)
            .where(Refund.id == refund_id)
            .with_for_update()
        )
        if not refund:
            raise LookupError("REFUND_NOT_FOUND")
        if refund.status == "COMPLETED":
            if (
                provider_refund_id
                and refund.provider_refund_id
                and refund.provider_refund_id != provider_refund_id.strip()
            ):
                raise ValueError("REFUND_PROVIDER_ID_MISMATCH")
            return refund
        if refund.status not in {"PENDING", "SUBMITTING", "PROCESSING"}:
            raise ValueError("REFUND_NOT_COMPLETABLE")
        if not provider_refund_id or not provider_refund_id.strip():
            raise ValueError("REFUND_PROVIDER_ID_REQUIRED")
        provider_refund_id = provider_refund_id.strip()
        provider_name = refund.provider

        reused = db.scalar(
            select(Refund.id).where(
                Refund.provider == provider_name,
                Refund.provider_refund_id == provider_refund_id,
                Refund.id != refund.id,
            )
        )
        if reused:
            raise ValueError("REFUND_PROVIDER_ID_REUSED")

        dispute = db.scalar(
            select(Dispute)
            .where(Dispute.id == refund.dispute_id)
            .with_for_update()
        )
        order = db.scalar(
            select(Order)
            .where(Order.id == refund.order_id)
            .with_for_update()
        )
        if not dispute or not order:
            raise ValueError("REFUND_AGGREGATE_INVALID")
        if order.status != OrderStatus.REFUNDING.value:
            raise ValueError("ORDER_NOT_REFUNDING")

        now = datetime.now(timezone.utc)
        refund.status = "COMPLETED"
        refund.provider_refund_id = provider_refund_id
        refund.completed_at = now
        dispute.status = "RESOLVED"
        dispute.resolution = "REFUND_CUSTOMER"
        dispute.resolved_by_user_id = admin_user_id
        dispute.resolved_at = now

        actor_type = "PLATFORM" if admin_user_id else "PAYMENT"
        actor_id = str(admin_user_id) if admin_user_id else None
        OrderService.transition(
            db,
            order,
            OrderStatus.REFUNDED,
            event_type="REFUND_COMPLETED",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "disputeId": str(dispute.id),
                "refundId": str(refund.id),
                "providerRefundId": provider_refund_id,
                "amount": refund.amount,
            },
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            reused = db.scalar(
                select(Refund.id).where(
                    Refund.provider == provider_name,
                    Refund.provider_refund_id == provider_refund_id,
                    Refund.id != refund_id,
                )
            )
            if reused:
                raise ValueError("REFUND_PROVIDER_ID_REUSED")
            raise
        db.refresh(refund)
        return refund

    @staticmethod
    def _actor_role(
        db: Session,
        *,
        order: Order,
        actor_user_id: uuid.UUID,
    ) -> str:
        if order.user_id == actor_user_id:
            return "USER"

        player = db.scalar(
            select(PlayerProfile).where(PlayerProfile.user_id == actor_user_id)
        )
        if player:
            assignment = db.scalar(
                select(OrderAssignment).where(
                    OrderAssignment.order_id == order.id,
                    OrderAssignment.player_id == player.id,
                    OrderAssignment.status == "ACTIVE",
                )
            )
            if assignment:
                return "PLAYER"
        raise PermissionError("DISPUTE_ACTOR_NOT_ORDER_PARTICIPANT")

    @staticmethod
    def _locked_open_dispute(
        db: Session,
        dispute_id: uuid.UUID,
    ) -> tuple[Dispute, Order]:
        dispute = db.scalar(
            select(Dispute)
            .where(Dispute.id == dispute_id)
            .with_for_update()
        )
        if not dispute:
            raise LookupError("DISPUTE_NOT_FOUND")
        if dispute.status == "RESOLVED":
            order = db.scalar(
                select(Order)
                .where(Order.id == dispute.order_id)
                .with_for_update()
            )
            return dispute, order
        if dispute.status != "OPEN":
            raise ValueError("DISPUTE_NOT_OPEN")

        order = db.scalar(
            select(Order)
            .where(Order.id == dispute.order_id)
            .with_for_update()
        )
        if not order or order.status != OrderStatus.DISPUTED.value:
            raise ValueError("ORDER_NOT_DISPUTED")
        return dispute, order
