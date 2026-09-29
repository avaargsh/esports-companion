from fastapi.testclient import TestClient

from app.main import app


def test_order_events_are_visible_only_to_order_participants():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        identities = client.get("/api/v1/dev/demo-identities").json()

        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]
        other_player_user_id = identities["players"][1]["userId"]
        sku_id = demo["games"][0]["skus"][0]["id"]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku_id, "quantity": 1, "remark": "timeline test"},
        )
        assert created.status_code == 201
        order = created.json()
        order_id = order["id"]

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"timeline-pay-{order_id}",
            },
        )
        assert paid.status_code == 200
        assert paid.json()["status"] == "MATCHING"

        customer_events = client.get(
            f"/api/v1/orders/{order_id}/events",
            headers={"X-User-Id": customer_id},
        )
        assert customer_events.status_code == 200
        events = customer_events.json()
        assert [item["event_type"] for item in events[:3]] == [
            "ORDER_CREATED",
            "PAYMENT_SUCCESS",
            "ORDER_ENTERED_MATCHING",
        ]
        assert all("actor_id" not in item for item in events)
        assert all("payload_json" not in item for item in events)

        unrelated = client.get(
            f"/api/v1/orders/{order_id}/events",
            headers={"X-User-Id": other_player_user_id},
        )
        assert unrelated.status_code == 403
        assert unrelated.json()["detail"] == "ORDER_ACCESS_DENIED"

        claimed = client.post(
            f"/api/v1/player/orders/{order_id}/claim",
            headers={"X-User-Id": player_user_id},
            json={"expected_version": paid.json()["version"]},
        )
        assert claimed.status_code == 200
        assert claimed.json()["status"] == "ACCEPTED"

        player_events = client.get(
            f"/api/v1/orders/{order_id}/events",
            headers={"X-User-Id": player_user_id},
        )
        assert player_events.status_code == 200
        assert player_events.json()[-1]["to_status"] == "ACCEPTED"


def test_order_events_return_404_for_unknown_order():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        response = client.get(
            "/api/v1/orders/00000000-0000-0000-0000-000000000001/events",
            headers={"X-User-Id": demo["customerUserId"]},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "ORDER_NOT_FOUND"
