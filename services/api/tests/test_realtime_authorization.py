import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import OrderAssignment, PlayerProfile
from app.realtime import ConnectionManager


def _accepted_order(client: TestClient):
    demo = client.get("/api/v1/dev/bootstrap").json()
    customer_id = demo["customerUserId"]
    player_user_id = demo["playerUserId"]
    identities = client.get("/api/v1/dev/demo-identities").json()
    other_player_user_id = identities["players"][1]["userId"]
    sku = demo["games"][0]["skus"][0]

    created = client.post(
        "/api/v1/orders",
        headers={"X-User-Id": customer_id},
        json={"sku_id": sku["id"], "quantity": 1, "remark": "ws-auth"},
    ).json()
    paid = client.post(
        f"/api/v1/orders/{created['id']}/mock-pay",
        headers={
            "X-User-Id": customer_id,
            "Idempotency-Key": f"ws-pay-{uuid.uuid4()}",
        },
    ).json()
    claimed = client.post(
        f"/api/v1/player/orders/{created['id']}/claim",
        headers={"X-User-Id": player_user_id},
        json={"expected_version": paid["version"]},
    )
    assert claimed.status_code == 200
    return created["id"], customer_id, player_user_id, other_player_user_id


def test_websocket_requires_identity_and_authorizes_order_channel():
    with TestClient(app) as client:
        order_id, customer_id, _player_id, outsider_id = _accepted_order(client)

        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws") as websocket:
                websocket.receive_json()
        assert exc.value.code == 4401

        with client.websocket_connect(
            f"/ws?user_id={customer_id}"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "subscribe",
                    "channels": [
                        f"order:{order_id}",
                        f"user:{customer_id}",
                    ],
                }
            )
            subscribed = websocket.receive_json()
            assert subscribed["type"] == "subscribed"
            assert f"order:{order_id}" in subscribed["channels"]
            assert f"user:{customer_id}" in subscribed["channels"]
            assert subscribed["rejected"] == []

        with client.websocket_connect(
            f"/ws?user_id={outsider_id}"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "subscribe",
                    "channels": [
                        f"order:{order_id}",
                        f"user:{customer_id}",
                    ],
                }
            )
            subscribed = websocket.receive_json()
            assert subscribed["channels"] == []
            assert f"order:{order_id}" in subscribed["rejected"]
            assert f"user:{customer_id}" in subscribed["rejected"]


def test_released_player_cannot_subscribe_to_future_order_events():
    with TestClient(app) as client:
        order_id, _customer_id, player_user_id, _outsider_id = _accepted_order(client)

        with client.websocket_connect(
            f"/ws?user_id={player_user_id}"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "subscribe",
                    "channels": [f"order:{order_id}"],
                }
            )
            subscribed = websocket.receive_json()
            assert subscribed["channels"] == [f"order:{order_id}"]

        with SessionLocal() as db:
            player = db.scalar(
                select(PlayerProfile).where(
                    PlayerProfile.user_id == uuid.UUID(player_user_id)
                )
            )
            assignment = db.scalar(
                select(OrderAssignment).where(
                    OrderAssignment.order_id == uuid.UUID(order_id),
                    OrderAssignment.player_id == player.id,
                    OrderAssignment.status == "ACTIVE",
                )
            )
            assignment.status = "RELEASED"
            assignment.released_at = datetime.now(timezone.utc)
            db.commit()

        with client.websocket_connect(
            f"/ws?user_id={player_user_id}"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "subscribe",
                    "channels": [f"order:{order_id}"],
                }
            )
            subscribed = websocket.receive_json()
            assert subscribed["channels"] == []
            assert subscribed["rejected"] == [f"order:{order_id}"]


class _FakeSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.messages.append(message)


def test_realtime_publish_filters_already_connected_released_participant():
    manager = ConnectionManager()
    customer = _FakeSocket()
    former_player = _FakeSocket()
    platform = _FakeSocket()
    customer_id = uuid.uuid4()
    former_player_id = uuid.uuid4()
    platform_id = uuid.uuid4()
    channel = f"order:{uuid.uuid4()}"

    async def scenario():
        await manager.connect(customer, user_id=customer_id, roles=("USER",))
        await manager.connect(
            former_player,
            user_id=former_player_id,
            roles=("PLAYER",),
        )
        await manager.connect(platform, user_id=platform_id, roles=("PLATFORM",))
        manager.subscribe(customer, [channel])
        manager.subscribe(former_player, [channel])
        manager.subscribe(platform, [channel])

        await manager.publish(
            [channel],
            {"type": "order.message_created"},
            order_allowed_user_ids={str(customer_id)},
        )

    asyncio.run(scenario())

    assert [item["type"] for item in customer.messages] == ["order.message_created"]
    assert former_player.messages == []
    assert [item["type"] for item in platform.messages] == ["order.message_created"]
