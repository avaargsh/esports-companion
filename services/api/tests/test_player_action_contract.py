from fastapi.testclient import TestClient

from app.main import app


def test_player_action_contract_controls_availability_and_claim_affordance():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()

        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]
        game = demo["games"][0]
        game_id = game["id"]
        sku_id = game["skus"][0]["id"]

        offline = client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "OFFLINE"},
        )
        assert offline.status_code == 200
        assert offline.json()["available_actions"] == ["GO_AVAILABLE"]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku_id, "quantity": 1, "remark": "player action contract"},
        )
        assert created.status_code == 201
        order_id = created.json()["id"]

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"player-actions-pay-{order_id}",
            },
        )
        assert paid.status_code == 200
        assert paid.json()["status"] == "MATCHING"

        offline_pool = client.get(
            f"/api/v1/player/order-pool?game_id={game_id}",
            headers={"X-User-Id": player_user_id},
        )
        assert offline_pool.status_code == 200
        pool_order = next(
            item for item in offline_pool.json()
            if item["id"] == order_id
        )
        assert pool_order["available_actions"] == []

        available = client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "AVAILABLE"},
        )
        assert available.status_code == 200
        assert available.json()["available_actions"] == ["GO_OFFLINE"]

        available_pool = client.get(
            f"/api/v1/player/order-pool?game_id={game_id}",
            headers={"X-User-Id": player_user_id},
        )
        assert available_pool.status_code == 200
        pool_order = next(
            item for item in available_pool.json()
            if item["id"] == order_id
        )
        assert pool_order["available_actions"] == ["CLAIM_ORDER"]
