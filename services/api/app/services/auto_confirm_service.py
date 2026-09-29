import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order
from app.services.order_service import OrderService
from app.services.settlement_service import SettlementService


class AutoConfirmService:
    @staticmethod
    def due_order_ids(
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
                    Order.status == OrderStatus.FINISH_REQUESTED.value,
                    Order.finish_requested_at.is_not(None),
                    Order.finish_requested_at <= cutoff,
                )
                .order_by(Order.finish_requested_at)
                .limit(limit)
            )
        )

    @staticmethod
    def auto_confirm_one(
        db: Session,
        *,
        order_id: uuid.UUID,
        now: datetime,
        timeout_seconds: int,
    ) -> bool:
        order = db.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if not order or order.status != OrderStatus.FINISH_REQUESTED.value:
            return False
        if order.finish_requested_at is None:
            return False

        requested_at = order.finish_requested_at
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=timezone.utc)
        else:
            requested_at = requested_at.astimezone(timezone.utc)

        cutoff = now.astimezone(timezone.utc) - timedelta(seconds=timeout_seconds)
        if requested_at > cutoff:
            return False

        OrderService.transition(
            db,
            order,
            OrderStatus.COMPLETED,
            event_type="AUTO_CONFIRM_FINISH",
            actor_type="SYSTEM",
            payload={"timeoutSeconds": timeout_seconds},
        )
        SettlementService.settle(db, order)
        return True

    @staticmethod
    def process_due(
        db: Session,
        *,
        now: datetime | None = None,
        timeout_seconds: int,
        limit: int = 100,
    ) -> list[uuid.UUID]:
        effective_now = now or datetime.now(timezone.utc)
        ids = AutoConfirmService.due_order_ids(
            db,
            now=effective_now,
            timeout_seconds=timeout_seconds,
            limit=limit,
        )
        return [
            order_id
            for order_id in ids
            if AutoConfirmService.auto_confirm_one(
                db,
                order_id=order_id,
                now=effective_now,
                timeout_seconds=timeout_seconds,
            )
        ]
