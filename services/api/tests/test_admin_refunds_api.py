import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_admin_manual_refund_completion_moves_order_to_refunded():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        identities = client.get("/api/v1/dev/demo-identities").json()
        customer_id = demo["customerUserId"]
        admin_id = identities["admin"]["userId"]
        sku_id = demo["games"][0]["skus"][0]["id"]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": f"manual-refund-{uuid.uuid4().hex}",
            },
        )
        assert created.status_code == 201
        order_id = created.json()["id"]

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"manual-refund-pay-{uuid.uuid4().hex}",
            },
        )
        assert paid.status_code == 200
        assert paid.json()["status"] == "MATCHING"

        opened = client.post(
            f"/api/v1/orders/{order_id}/disputes",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"manual-refund-dispute-{uuid.uuid4().hex}",
            },
            json={
                "reason_code": "CANCEL_BEFORE_SERVICE",
                "description": "customer requested refund before matching",
            },
        )
        assert opened.status_code == 201
        dispute_id = opened.json()["id"]

        approved = client.post(
            f"/api/v1/admin/disputes/{dispute_id}/refund",
            headers={"X-Admin-Id": admin_id},
        )
        assert approved.status_code == 200
        refund = approved.json()
        assert refund["provider"] == "MANUAL"
        assert refund["status"] == "PENDING"

        missing_reference = client.post(
            f"/api/v1/admin/refunds/{refund['id']}/complete",
            headers={"X-Admin-Id": admin_id},
        )
        assert missing_reference.status_code == 422

        blank_reference = client.post(
            f"/api/v1/admin/refunds/{refund['id']}/complete",
            headers={"X-Admin-Id": admin_id},
            json={"provider_refund_id": "   "},
        )
        assert blank_reference.status_code == 409

        provider_refund_id = f"manual-refund-{uuid.uuid4().hex}"
        completed = client.post(
            f"/api/v1/admin/refunds/{refund['id']}/complete",
            headers={"X-Admin-Id": admin_id},
            json={"provider_refund_id": provider_refund_id},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"
        assert completed.json()["provider_refund_id"] == provider_refund_id

        order = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"X-Admin-Id": admin_id},
        )
        assert order.status_code == 200
        assert order.json()["status"] == "REFUNDED"

        disputes = client.get(
            "/api/v1/admin/disputes",
            headers={"X-Admin-Id": admin_id},
        )
        assert disputes.status_code == 200
        dispute = next(item for item in disputes.json() if item["id"] == dispute_id)
        assert dispute["status"] == "RESOLVED"
        assert dispute["resolution"] == "REFUND_CUSTOMER"

        refunds = client.get(
            "/api/v1/admin/refunds",
            headers={"X-Admin-Id": admin_id},
        )
        assert refunds.status_code == 200
        listed_refund = next(item for item in refunds.json() if item["id"] == refund["id"])
        assert listed_refund["status"] == "COMPLETED"
        assert listed_refund["provider_refund_id"] == provider_refund_id
