from fastapi.testclient import TestClient

from app.main import app


def test_order_available_actions_follow_customer_state_and_viewer_role():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()

        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]
        sku_id = demo["games"][0]["skus"][0]["id"]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku_id, "quantity": 1, "remark": "action contract"},
        )
        assert created.status_code == 201
        order = created.json()
        order_id = order["id"]

        waiting = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": customer_id},
        )
        assert waiting.status_code == 200
        assert waiting.json()["available_actions"] == ["PAY", "CANCEL"]

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"actions-pay-{order_id}",
            },
        )
        assert paid.status_code == 200
        assert paid.json()["status"] == "MATCHING"

        matching = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": customer_id},
        )
        assert matching.json()["available_actions"] == ["REQUEST_REFUND"]

        claimed = client.post(
            f"/api/v1/player/orders/{order_id}/claim",
            headers={"X-User-Id": player_user_id},
            json={"expected_version": paid.json()["version"]},
        )
        assert claimed.status_code == 200
        assert claimed.json()["status"] == "ACCEPTED"

        player_view = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": player_user_id},
        )
        assert player_view.status_code == 200
        assert player_view.json()["available_actions"] == []

        accepted = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": customer_id},
        )
        assert accepted.json()["available_actions"] == [
            "REQUEST_REFUND",
            "OPEN_DISPUTE",
        ]

        started = client.post(
            f"/api/v1/player/orders/{order_id}/start",
            headers={"X-User-Id": player_user_id},
        )
        assert started.status_code == 200
        assert started.json()["status"] == "IN_SERVICE"

        in_service = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": customer_id},
        )
        assert in_service.json()["available_actions"] == ["OPEN_DISPUTE"]

        finished = client.post(
            f"/api/v1/player/orders/{order_id}/finish",
            headers={"X-User-Id": player_user_id},
        )
        assert finished.status_code == 200
        assert finished.json()["status"] == "FINISH_REQUESTED"

        awaiting_confirmation = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": customer_id},
        )
        assert awaiting_confirmation.json()["available_actions"] == [
            "CONFIRM_FINISH",
            "OPEN_DISPUTE",
        ]

        confirmed = client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers={"X-User-Id": customer_id},
        )
        assert confirmed.status_code == 200

        terminal = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": customer_id},
        )
        assert terminal.json()["available_actions"] == []
