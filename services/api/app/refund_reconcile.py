import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Refund
from app.providers.registry import get_refund_provider
from app.services.refund_service import RefundService

logger = logging.getLogger(__name__)


def _candidate_ids() -> list[uuid.UUID]:
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.refund_reconcile_min_age_seconds
    )
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Refund.id)
                .where(
                    Refund.provider == "WECHAT",
                    Refund.status.in_(["SUBMITTING", "PROCESSING"]),
                    Refund.out_refund_no.is_not(None),
                    Refund.updated_at <= cutoff,
                )
                .order_by(Refund.updated_at)
                .limit(settings.refund_reconcile_batch_size)
            )
        )


def _reconcile_one(refund_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        try:
            RefundService.reconcile(
                db,
                refund_id=refund_id,
                provider=get_refund_provider("wechat"),
                min_age_seconds=settings.refund_reconcile_min_age_seconds,
            )
        except Exception:
            db.rollback()
            logger.exception("refund reconciliation failed for %s", refund_id)


async def run_refund_reconcile_worker() -> None:
    while True:
        try:
            if settings.refund_provider.strip().lower() == "wechat":
                for refund_id in await asyncio.to_thread(_candidate_ids):
                    await asyncio.to_thread(_reconcile_one, refund_id)
        except Exception:
            logger.exception("refund reconciliation scan failed")
        await asyncio.sleep(max(1, settings.refund_reconcile_scan_seconds))
