import uuid

from fastapi.testclient import TestClient

from app.main import app


def _create_order(client: TestClient):
    demo = client.get("/api/v1/dev/bootstrap").json()
    identities = client.get("/api/v1/dev/demo-identities").json()
    sku_id = demo["games"][0]["skus"][0]["id"]
    created = client.post(
        "/api/v1/orders",
        headers={"X-User-Id": demo["customerUserId"]},
        json={
            "sku_id": sku_id,
            "quantity": 1,
            "remark": f"authz-contract-{uuid.uuid4().hex}",
        },
    )
    assert created.status_code == 201
    return demo, identities, created.json()


def test_outsider_is_denied_before_order_state_is_exposed():
    with TestClient(app) as client:
        demo, identities, order = _create_order(client)
        outsider_id = identities["players"][1]["userId"]
        order_id = order["id"]

        owner_message = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": demo["customerUserId"]},
            json={
                "client_message_id": f"owner-{uuid.uuid4().hex}",
                "content": "not sendable yet",
            },
        )
        assert owner_message.status_code == 409
        assert owner_message.json()["detail"] == "ORDER_CHAT_NOT_SENDABLE"

        outsider_message = client.post(
            f"/api/v1/orders/{order_id}/messages",
            headers={"X-User-Id": outsider_id},
            json={
                "client_message_id": f"outsider-{uuid.uuid4().hex}",
                "content": "probe",
            },
        )
        assert outsider_message.status_code == 403
        assert outsider_message.json()["detail"] == "ORDER_MESSAGE_ACCESS_DENIED"

        owner_dispute = client.post(
            f"/api/v1/orders/{order_id}/disputes",
            headers={
                "X-User-Id": demo["customerUserId"],
                "Idempotency-Key": f"owner-dispute-{uuid.uuid4().hex}",
            },
            json={
                "reason_code": "SERVICE_QUALITY",
                "description": "not disputable yet",
            },
        )
        assert owner_dispute.status_code == 409
        assert owner_dispute.json()["detail"] == "ORDER_NOT_DISPUTABLE"

        outsider_dispute = client.post(
            f"/api/v1/orders/{order_id}/disputes",
            headers={
                "X-User-Id": outsider_id,
                "Idempotency-Key": f"outsider-dispute-{uuid.uuid4().hex}",
            },
            json={
                "reason_code": "SERVICE_QUALITY",
                "description": "probe",
            },
        )
        assert outsider_dispute.status_code == 403
        assert (
            outsider_dispute.json()["detail"]
            == "DISPUTE_ACTOR_NOT_ORDER_PARTICIPANT"
        )


def test_owner_only_actions_deny_non_owner_before_business_state_checks():
    with TestClient(app) as client:
        demo, identities, order = _create_order(client)
        outsider_id = identities["players"][1]["userId"]
        order_id = order["id"]

        payment = client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={
                "X-User-Id": outsider_id,
                "Idempotency-Key": f"outsider-pay-{uuid.uuid4().hex}",
            },
        )
        assert payment.status_code == 403
        assert payment.json()["detail"] == "ORDER_NOT_OWNED"

        review = client.post(
            f"/api/v1/orders/{order_id}/reviews",
            headers={"X-User-Id": outsider_id},
            json={"rating": 5, "content": "probe"},
        )
        assert review.status_code == 403
        assert review.json()["detail"] == "ORDER_NOT_OWNED"


def test_active_participant_and_platform_share_order_view_contract():
    with TestClient(app) as client:
        demo, identities, order = _create_order(client)
        customer_id = demo["customerUserId"]
        player_id = demo["playerUserId"]
        outsider_id = identities["players"][1]["userId"]
        admin_id = identities["admin"]["userId"]
        order_id = order["id"]

        outsider = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": outsider_id},
        )
        assert outsider.status_code == 403
        assert outsider.json()["detail"] == "ORDER_ACCESS_DENIED"

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"authz-pay-{uuid.uuid4().hex}",
            },
        )
        assert paid.status_code == 200

        claimed = client.post(
            f"/api/v1/player/orders/{order_id}/claim",
            headers={"X-User-Id": player_id},
            json={"expected_version": paid.json()["version"]},
        )
        assert claimed.status_code == 200

        player_view = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-User-Id": player_id},
        )
        assert player_view.status_code == 200

        platform_view = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-Admin-Id": admin_id},
        )
        assert platform_view.status_code == 200
