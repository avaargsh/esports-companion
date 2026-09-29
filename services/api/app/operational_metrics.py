import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.metrics import (
    DISPUTES_OLDEST_OPEN_SECONDS,
    DISPUTES_OPEN,
    FINISH_REQUESTS_OLDEST_SECONDS,
    FINISH_REQUESTS_OVERDUE,
    FINISH_REQUESTS_PENDING,
    OPERATIONAL_METRICS_SCAN_SUCCESS,
    OUTBOX_OLDEST_PENDING_SECONDS,
    OUTBOX_PENDING,
    REFUNDS_INFLIGHT,
    REFUNDS_OLDEST_INFLIGHT_SECONDS,
    WITHDRAWALS_OLDEST_PENDING_SECONDS,
    WITHDRAWALS_PENDING,
)
from app.models import Dispute, Order, OutboxEvent, Refund, Withdrawal

logger = logging.getLogger(__name__)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_seconds(now: datetime, oldest: datetime | None) -> float:
    value = _as_utc(oldest)
    if value is None:
        return 0.0
    return max(0.0, (now - value).total_seconds())


def refresh_operational_metrics(*, now: datetime | None = None) -> None:
    effective_now = now or datetime.now(timezone.utc)
    try:
        with SessionLocal() as db:
            outbox_count, outbox_oldest = db.execute(
                select(
                    func.count(OutboxEvent.id),
                    func.min(OutboxEvent.created_at),
                ).where(OutboxEvent.status == "PENDING")
            ).one()

            refund_count, refund_oldest = db.execute(
                select(
                    func.count(Refund.id),
                    func.min(Refund.updated_at),
                ).where(
                    Refund.status.in_(["PENDING", "SUBMITTING", "PROCESSING"])
                )
            ).one()

            withdrawal_count, withdrawal_oldest = db.execute(
                select(
                    func.count(Withdrawal.id),
                    func.min(Withdrawal.created_at),
                ).where(Withdrawal.status == "PENDING")
            ).one()

            dispute_count, dispute_oldest = db.execute(
                select(
                    func.count(Dispute.id),
                    func.min(Dispute.created_at),
                ).where(Dispute.status.in_(["OPEN", "RESOLVING"]))
            ).one()

            finish_count, finish_oldest = db.execute(
                select(
                    func.count(Order.id),
                    func.min(Order.finish_requested_at),
                ).where(Order.status == "FINISH_REQUESTED")
            ).one()
            finish_deadline = (
                effective_now
                - timedelta(
                    seconds=max(
                        1,
                        settings.finish_confirm_timeout_seconds
                        + settings.order_timeout_scan_seconds,
                    )
                )
            )
            finish_overdue = db.scalar(
                select(func.count(Order.id)).where(
                    Order.status == "FINISH_REQUESTED",
                    Order.finish_requested_at.is_not(None),
                    Order.finish_requested_at < finish_deadline,
                )
            )

        OUTBOX_PENDING.set(outbox_count or 0)
        OUTBOX_OLDEST_PENDING_SECONDS.set(
            _age_seconds(effective_now, outbox_oldest)
        )
        REFUNDS_INFLIGHT.set(refund_count or 0)
        REFUNDS_OLDEST_INFLIGHT_SECONDS.set(
            _age_seconds(effective_now, refund_oldest)
        )
        WITHDRAWALS_PENDING.set(withdrawal_count or 0)
        WITHDRAWALS_OLDEST_PENDING_SECONDS.set(
            _age_seconds(effective_now, withdrawal_oldest)
        )
        DISPUTES_OPEN.set(dispute_count or 0)
        DISPUTES_OLDEST_OPEN_SECONDS.set(
            _age_seconds(effective_now, dispute_oldest)
        )
        FINISH_REQUESTS_PENDING.set(finish_count or 0)
        FINISH_REQUESTS_OVERDUE.set(finish_overdue or 0)
        FINISH_REQUESTS_OLDEST_SECONDS.set(
            _age_seconds(effective_now, finish_oldest)
        )
        OPERATIONAL_METRICS_SCAN_SUCCESS.set(1)
    except Exception:
        OPERATIONAL_METRICS_SCAN_SUCCESS.set(0)
        logger.exception("operational metrics scan failed")


async def run_operational_metrics_worker() -> None:
    while True:
        await asyncio.to_thread(refresh_operational_metrics)
        await asyncio.sleep(max(1, settings.operational_metrics_scan_seconds))
