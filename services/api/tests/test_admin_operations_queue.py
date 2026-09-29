from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import Game, Order, OutboxEvent, ServiceSKU, User
from app.services.operations_queue_service import build_operations_queue


def test_operations_queue_surfaces_sla_breaches_without_persisting_fixture():
    now = datetime.now(timezone.utc)
    suffix = uuid4().hex[:8]

    with SessionLocal() as db:
        user = User(nickname=f"ops-queue-user-{suffix}")
        game = Game(
            code=f"ops-queue-{suffix}",
            name=f"Ops Queue {suffix}",
            status="ACTIVE",
        )
        db.add_all([user, game])
        db.flush()

        sku = ServiceSKU(
            game_id=game.id,
            name=f"Ops Queue SKU {suffix}",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=100,
            platform_fee_rate=Decimal("0.2000"),
            status="ACTIVE",
        )
        db.add(sku)
        db.flush()

        order = Order(
            order_no=f"ORD_OPS_QUEUE_{suffix.upper()}",
            user_id=user.id,
            game_id=game.id,
            sku_id=sku.id,
            status="FINISH_REQUESTED",
            quantity=1,
            unit_price=100,
            total_amount=100,
            player_amount=80,
            platform_fee=20,
            remark="ops queue fixture",
            finish_requested_at=now
            - timedelta(
                seconds=settings.finish_confirm_timeout_seconds
                + settings.order_timeout_scan_seconds
                + 30
            ),
        )
        db.add(order)
        db.flush()

        outbox = OutboxEvent(
            aggregate_type="ORDER",
            aggregate_id=str(order.id),
            event_type="OPS_QUEUE_TEST",
            payload_json={},
            status="PENDING",
            created_at=now - timedelta(minutes=3),
        )
        db.add(outbox)
        db.flush()

        payload = build_operations_queue(db, now=now)
        order_id = str(order.id)

        kinds = {item["kind"] for item in payload["items"]}
        assert "OUTBOX" in kinds
        assert "FINISH_REQUESTED" in kinds
        assert any(
            item["kind"] == "FINISH_REQUESTED" and item["orderId"] == order_id
            for item in payload["items"]
        )

        finish_category = next(
            item
            for item in payload["categories"]
            if item["kind"] == "FINISH_REQUESTED"
        )
        assert finish_category["count"] >= 1
        assert finish_category["breachedCount"] >= 1

        db.rollback()


def test_operations_queue_endpoint_requires_platform_role():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        identities = client.get("/api/v1/dev/demo-identities").json()

        platform = client.get(
            "/api/v1/admin/operations/queue",
            headers={"X-Admin-Id": identities["admin"]["userId"]},
        )
        assert platform.status_code == 200
        assert "categories" in platform.json()
        assert "items" in platform.json()

        customer = client.get(
            "/api/v1/admin/operations/queue",
            headers={"X-User-Id": demo["customerUserId"]},
        )
        assert customer.status_code == 403
