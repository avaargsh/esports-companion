import asyncio
import logging

from app.config import settings
from app.db import SessionLocal
from app.services.auto_confirm_service import AutoConfirmService

logger = logging.getLogger(__name__)


def scan_due_orders() -> int:
    with SessionLocal() as db:
        try:
            return len(
                AutoConfirmService.process_due(
                    db,
                    timeout_seconds=settings.finish_confirm_timeout_seconds,
                    limit=settings.order_timeout_batch_size,
                )
            )
        except Exception:
            db.rollback()
            logger.exception("order timeout scan failed")
            return 0


async def run_timeout_scanner() -> None:
    while True:
        await asyncio.to_thread(scan_due_orders)
        await asyncio.sleep(max(1, settings.order_timeout_scan_seconds))
