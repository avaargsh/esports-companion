import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import OrderAssignment, OrderMessage, PlayerProfile


def _bootstrap(client: TestClient):
    demo = client.get("/api/v1/dev/bootstrap").json()
    game = demo["games"][0]
    sku = game["skus"][0]
    return demo, game, sku


def _create_matching_order(client: TestClient, customer_id: str, sku_id: str):
    created = client.post(
        "/api/v1/orders",
        headers={"X-User-Id": customer_id},
        json={
            "sku_id": sku_id,
            "quantity": 1,
            "remark": "message-test",
        },
    )
    assert created.status_code == 201
    order = created.json()

    paid = client.post(
        f"/api/v1/orders/{order['id']}/mock-pay",
        headers={
            "X-User-Id": customer_id,
            "Idempotency-Key": f"message-pay-{uuid.uuid4()}",
        },
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "MATCHING"
    return paid.json()


def _claim(
    client: TestClient,
    *,
    order_id: str,
    player_user_id: str,
    version: int,
):
    claimed = client.post(
        f"/api/v1/player/orders/{order_id}/claim",
        headers={"X-User-Id": player_user_id},
        json={"expected_version": version},
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "ACCEPTED"
    return claimed.json()


def test_order_chat_requires_assignment_and_is_idempotent():
    with TestClient(app) as client:
        demo, _game, sku = _bootstrap(client)
        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]
        identities = client.get("/api/v1/dev/demo-identities").json()
        other_player_user_id = identities["players"][1]["userId"]

        matching = _create_matching_order(
            client,
            customer_id,
            sku["id"],
        )
        order_id = matching["id"]

        before_assignment = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
            json={
                "client_message_id": "before-assignment",
                "content": "hello?",
            },
        )
        assert before_assignment.status_code == 409
        assert before_assignment.json()["detail"] == "ORDER_CHAT_NOT_SENDABLE"

        _claim(
            client,
            order_id=order_id,
            player_user_id=player_user_id,
            version=matching["version"],
        )

        first = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
            json={
                "client_message_id": "customer-1",
                "content": "  可以现在开始吗？  ",
            },
        )
        assert first.status_code == 201
        first_message = first.json()
        assert first_message["sender_role"] == "USER"
        assert first_message["content"] == "可以现在开始吗？"

        replay = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
            json={
                "client_message_id": "customer-1",
                "content": "可以现在开始吗？",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == first_message["id"]

        player_reply = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": player_user_id},
            json={
                "client_message_id": "player-1",
                "content": "可以，马上开始。",
            },
        )
        assert player_reply.status_code == 201
        assert player_reply.json()["sender_role"] == "PLAYER"

        customer_messages = client.get(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
        )
        assert customer_messages.status_code == 200
        assert [item["content"] for item in customer_messages.json()] == [
            "可以现在开始吗？",
            "可以，马上开始。",
        ]

        player_messages = client.get(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": player_user_id},
        )
        assert player_messages.status_code == 200
        assert len(player_messages.json()) == 2

        outsider = client.get(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": other_player_user_id},
        )
        assert outsider.status_code == 403
        assert outsider.json()["detail"] == "ORDER_MESSAGE_ACCESS_DENIED"

        with SessionLocal() as db:
            count = len(
                list(
                    db.scalars(
                        select(OrderMessage).where(
                            OrderMessage.order_id == uuid.UUID(order_id)
                        )
                    )
                )
            )
            assert count == 2


def test_former_assigned_player_can_read_history_but_cannot_send():
    with TestClient(app) as client:
        demo, _game, sku = _bootstrap(client)
        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]

        matching = _create_matching_order(client, customer_id, sku["id"])
        order_id = matching["id"]
        _claim(
            client,
            order_id=order_id,
            player_user_id=player_user_id,
            version=matching["version"],
        )

        sent = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": player_user_id},
            json={
                "client_message_id": "history-1",
                "content": "历史消息",
            },
        )
        assert sent.status_code == 201

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
            db.commit()

        history = client.get(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": player_user_id},
        )
        assert history.status_code == 200
        assert [item["content"] for item in history.json()] == ["历史消息"]

        blocked = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": player_user_id},
            json={
                "client_message_id": "history-2",
                "content": "不应发送",
            },
        )
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "ORDER_MESSAGE_ACCESS_DENIED"



def test_terminal_order_keeps_message_history_but_rejects_new_messages():
    with TestClient(app) as client:
        demo, _game, sku = _bootstrap(client)
        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]

        matching = _create_matching_order(client, customer_id, sku["id"])
        order_id = matching["id"]
        _claim(
            client,
            order_id=order_id,
            player_user_id=player_user_id,
            version=matching["version"],
        )

        sent = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
            json={
                "client_message_id": f"terminal-history-{uuid.uuid4()}",
                "content": "这条消息需要在订单结束后继续可查。",
            },
        )
        assert sent.status_code == 201

        started = client.post(
            f"/api/v1/player/orders/{order_id}/start",
            headers={"X-User-Id": player_user_id},
        )
        assert started.status_code == 200

        finished = client.post(
            f"/api/v1/player/orders/{order_id}/finish",
            headers={"X-User-Id": player_user_id},
        )
        assert finished.status_code == 200

        confirmed = client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers={"X-User-Id": customer_id},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "SETTLED"

        history = client.get(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
        )
        assert history.status_code == 200
        assert any(
            item["content"] == "这条消息需要在订单结束后继续可查。"
            for item in history.json()
        )

        blocked = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": customer_id},
            json={
                "client_message_id": f"terminal-blocked-{uuid.uuid4()}",
                "content": "终态不应继续发消息",
            },
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "ORDER_CHAT_NOT_SENDABLE"
