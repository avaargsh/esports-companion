import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order
from app.services.completion_service import CompletionService


class AutoConfirmService:
    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def process_one_due(
        db: Session,
        *,
        now: datetime,
        timeout_seconds: int,
    ) -> uuid.UUID | None:
        cutoff = AutoConfirmService._as_utc(now) - timedelta(
            seconds=timeout_seconds
        )
        order = db.scalar(
            select(Order)
            .where(
                Order.status == OrderStatus.FINISH_REQUESTED.value,
                Order.finish_requested_at.is_not(None),
                Order.finish_requested_at <= cutoff,
            )
            .order_by(Order.finish_requested_at, Order.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not order:
            return None

        requested_at = AutoConfirmService._as_utc(order.finish_requested_at)
        CompletionService.complete_and_settle(
            db,
            order=order,
            event_type="AUTO_CONFIRM_FINISH",
            actor_type="SYSTEM",
            actor_id=None,
            payload={
                "finishRequestedAt": requested_at.isoformat(),
                "timeoutSeconds": timeout_seconds,
            },
        )
        return order.id

    @staticmethod
    def process_due(
        db: Session,
        *,
        now: datetime | None = None,
        timeout_seconds: int,
        limit: int = 100,
    ) -> list[uuid.UUID]:
        effective_now = now or datetime.now(timezone.utc)
        processed: list[uuid.UUID] = []
        for _ in range(max(1, limit)):
            order_id = AutoConfirmService.process_one_due(
                db,
                now=effective_now,
                timeout_seconds=timeout_seconds,
            )
            if order_id is None:
                break
            processed.append(order_id)
        return processed
