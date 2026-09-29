import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


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
