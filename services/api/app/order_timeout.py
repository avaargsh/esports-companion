import asyncio
import logging

from app.config import settings
from app.db import SessionLocal
from app.services.auto_confirm_service import AutoConfirmService

logger = logging.getLogger(__name__)


def scan_due_orders() -> int:
    with SessionLocal() as db:
        return len(
            AutoConfirmService.process_due(
                db,
                timeout_seconds=settings.finish_confirm_timeout_seconds,
            )
        )


async def run_timeout_scanner() -> None:
    while True:
        try:
            await asyncio.to_thread(scan_due_orders)
        except Exception:
            logger.exception("order timeout scan failed")
        await asyncio.sleep(settings.order_timeout_scan_seconds)
