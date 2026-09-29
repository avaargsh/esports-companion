import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.db import SessionLocal
from app.services.auto_confirm_service import AutoConfirmService

logger = logging.getLogger(__name__)


def _process_due_batch() -> int:
    with SessionLocal() as db:
        try:
            processed = AutoConfirmService.process_due(
                db,
                now=datetime.now(timezone.utc),
                timeout_seconds=settings.finish_confirm_timeout_seconds,
                limit=settings.order_timeout_batch_size,
            )
            return len(processed)
        except Exception:
            db.rollback()
            logger.exception("order timeout scan failed")
            return 0


async def run_order_timeout_worker() -> None:
    while True:
        await asyncio.to_thread(_process_due_batch)
        await asyncio.sleep(max(1, settings.order_timeout_scan_seconds))
