from fastapi.testclient import TestClient

from app.main import app


def test_wallet_action_contract_tracks_settlement_and_full_withdrawal():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()

        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]
        sku_id = demo["games"][0]["skus"][0]["id"]

        client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "AVAILABLE"},
        )

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku_id, "quantity": 1, "remark": "wallet actions"},
        )
        assert created.status_code == 201
        order_id = created.json()["id"]

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"wallet-actions-pay-{order_id}",
            },
        )
        assert paid.status_code == 200

        claimed = client.post(
            f"/api/v1/player/orders/{order_id}/claim",
            headers={"X-User-Id": player_user_id},
            json={"expected_version": paid.json()["version"]},
        )
        assert claimed.status_code == 200

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

        funded = client.get(
            "/api/v1/wallet",
            headers={"X-User-Id": player_user_id},
        )
        assert funded.status_code == 200
        wallet = funded.json()
        assert wallet["availableBalance"] > 0
        assert wallet["availableActions"] == ["REQUEST_WITHDRAWAL"]

        amount = wallet["availableBalance"]
        requested = client.post(
            "/api/v1/withdrawals",
            headers={
                "X-User-Id": player_user_id,
                "Idempotency-Key": f"wallet-actions-withdraw-{order_id}",
            },
            json={"amount": amount},
        )
        assert requested.status_code == 201

        frozen = client.get(
            "/api/v1/wallet",
            headers={"X-User-Id": player_user_id},
        )
        assert frozen.status_code == 200
        assert frozen.json()["availableBalance"] == 0
        assert frozen.json()["frozenBalance"] >= amount
        assert frozen.json()["availableActions"] == []
