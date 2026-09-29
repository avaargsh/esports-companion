import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, OrderAssignment
from app.services.order_service import OrderService


class AftercareService:
    @staticmethod
    def _release_assignment(
        db: Session,
        *,
        order_id: uuid.UUID,
        released_at: datetime,
    ) -> OrderAssignment | None:
        assignment = db.scalar(
            select(OrderAssignment)
            .where(
                OrderAssignment.order_id == order_id,
                OrderAssignment.status == "ACTIVE",
            )
            .with_for_update()
        )
        if not assignment:
            return None
        assignment.status = "RELEASED"
        assignment.released_at = released_at
        return assignment

    @staticmethod
    def due_assignment_ids(
        db: Session,
        *,
        now: datetime,
        timeout_seconds: int,
        limit: int = 100,
    ) -> list[uuid.UUID]:
        cutoff = now - timedelta(seconds=timeout_seconds)
        return list(
            db.scalars(
                select(Order.id)
                .where(
                    Order.status == OrderStatus.ACCEPTED.value,
                    Order.accepted_at.is_not(None),
                    Order.accepted_at <= cutoff,
                )
                .order_by(Order.accepted_at, Order.id)
                .limit(limit)
            )
        )

    @staticmethod
    def requeue_one(
        db: Session,
        *,
        order_id: uuid.UUID,
        now: datetime,
        timeout_seconds: int,
    ) -> bool:
        order = db.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if not order or order.status != OrderStatus.ACCEPTED.value:
            return False
        if order.accepted_at is None:
            return False

        accepted_at = order.accepted_at
        if accepted_at.tzinfo is None:
            accepted_at = accepted_at.replace(tzinfo=timezone.utc)
        else:
            accepted_at = accepted_at.astimezone(timezone.utc)

        effective_now = now.astimezone(timezone.utc)
        cutoff = effective_now - timedelta(seconds=timeout_seconds)
        if accepted_at > cutoff:
            return False

        assignment = AftercareService._release_assignment(
            db,
            order_id=order.id,
            released_at=effective_now,
        )
        previous_player_id = assignment.player_id if assignment else order.designated_player_id
        order.designated_player_id = None
        OrderService.transition(
            db,
            order,
            OrderStatus.MATCHING,
            event_type="ASSIGNMENT_TIMED_OUT",
            actor_type="SYSTEM",
            payload={
                "playerId": str(previous_player_id) if previous_player_id else None,
                "timeoutSeconds": timeout_seconds,
            },
        )
        db.commit()
        return True

    @staticmethod
    def process_due_assignments(
        db: Session,
        *,
        now: datetime | None = None,
        timeout_seconds: int,
        limit: int = 100,
    ) -> list[uuid.UUID]:
        effective_now = now or datetime.now(timezone.utc)
        ids = AftercareService.due_assignment_ids(
            db,
            now=effective_now,
            timeout_seconds=timeout_seconds,
            limit=limit,
        )
        return [
            order_id
            for order_id in ids
            if AftercareService.requeue_one(
                db,
                order_id=order_id,
                now=effective_now,
                timeout_seconds=timeout_seconds,
            )
        ]
