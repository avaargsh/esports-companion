import asyncio
import logging

from app.config import settings
from app.db import SessionLocal
from app.infrastructure import redis_client
from app.models import Order
from app.services.aftercare_service import AftercareService
from app.services.auto_confirm_service import AutoConfirmService

logger = logging.getLogger(__name__)


def scan_due_orders() -> int:
    processed = 0
    with SessionLocal() as db:
        try:
            processed += len(
                AutoConfirmService.process_due(
                    db,
                    timeout_seconds=settings.finish_confirm_timeout_seconds,
                    limit=settings.order_timeout_batch_size,
                )
            )
        except Exception:
            db.rollback()
            logger.exception("finish auto-confirm scan failed")

    with SessionLocal() as db:
        try:
            requeued = AftercareService.process_due_assignments(
                db,
                timeout_seconds=settings.assignment_start_timeout_seconds,
                limit=settings.order_timeout_batch_size,
            )
            processed += len(requeued)
            for order_id in requeued:
                order = db.get(Order, order_id)
                if not order:
                    continue
                try:
                    redis_client.zadd(
                        f"order_pool:{order.game_id}",
                        {str(order.id): order.created_at.timestamp()},
                    )
                except Exception:
                    logger.exception("failed to return timed-out order to redis pool")
        except Exception:
            db.rollback()
            logger.exception("assignment timeout scan failed")
    return processed


async def run_timeout_scanner() -> None:
    while True:
        await asyncio.to_thread(scan_due_orders)
        await asyncio.sleep(max(1, settings.order_timeout_scan_seconds))
