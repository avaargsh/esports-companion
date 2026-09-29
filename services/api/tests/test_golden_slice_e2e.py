import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_golden_slice_end_to_end():
    with TestClient(app) as client:
        bootstrap = client.get("/api/v1/dev/bootstrap")
        assert bootstrap.status_code == 200
        demo = bootstrap.json()

        customer_id = demo["customerUserId"]
        player_id = demo["playerUserId"]
        game = demo["games"][0]
        sku = game["skus"][0]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku["id"], "quantity": 1, "remark": "golden-slice-e2e"},
        )
        assert created.status_code == 201
        order = created.json()
        order_id = order["id"]
        assert order["status"] == "WAITING_PAYMENT"
        assert order["total_amount"] == 3000

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={"Idempotency-Key": f"e2e-{uuid.uuid4()}"},
        )
        assert paid.status_code == 200
        matching = paid.json()
        assert matching["status"] == "MATCHING"

        pool = client.get(
            "/api/v1/player/order-pool",
            params={"game_id": game["id"]},
        )
        assert pool.status_code == 200
        assert any(item["id"] == order_id for item in pool.json())

        claimed = client.post(
            f"/api/v1/player/orders/{order_id}/claim",
            headers={"X-User-Id": player_id},
            json={"expected_version": matching["version"]},
        )
        assert claimed.status_code == 200
        assert claimed.json()["status"] == "ACCEPTED"

        started = client.post(
            f"/api/v1/player/orders/{order_id}/start",
            headers={"X-User-Id": player_id},
        )
        assert started.status_code == 200
        assert started.json()["status"] == "IN_SERVICE"

        finished = client.post(
            f"/api/v1/player/orders/{order_id}/finish",
            headers={"X-User-Id": player_id},
        )
        assert finished.status_code == 200
        assert finished.json()["status"] == "FINISH_REQUESTED"

        confirmed = client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers={"X-User-Id": customer_id},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "SETTLED"

        reviewed = client.post(
            f"/api/v1/orders/{order_id}/reviews",
            headers={"X-User-Id": customer_id},
            json={"rating": 5, "content": "Golden Slice verified"},
        )
        assert reviewed.status_code == 201
        assert reviewed.json()["rating"] == 5

        wallet = client.get(
            "/api/v1/wallet",
            headers={"X-User-Id": player_id},
        )
        assert wallet.status_code == 200
        assert wallet.json()["availableBalance"] >= 2400

        ledger = client.get(
            "/api/v1/wallet/ledger",
            headers={"X-User-Id": player_id},
        )
        assert ledger.status_code == 200
        assert any(
            item["bizId"] == order_id
            and item["entryType"] == "PROVIDER_INCOME"
            and item["amount"] == 2400
            for item in ledger.json()
        )
