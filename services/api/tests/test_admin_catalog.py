import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_platform_can_manage_catalog():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        admin_id = demo["adminUserId"]
        headers = {"X-Admin-Id": admin_id}
        code = f"catalog-{uuid.uuid4().hex[:8]}"

        created_game = client.post(
            "/api/v1/admin/catalog/games",
            headers=headers,
            json={
                "code": code,
                "name": "Catalog Test",
                "sort_order": 99,
            },
        )
        assert created_game.status_code == 201
        game_id = created_game.json()["id"]

        created_sku = client.post(
            "/api/v1/admin/catalog/skus",
            headers=headers,
            json={
                "game_id": game_id,
                "name": "Catalog Test 1h",
                "service_type": "ENTERTAINMENT",
                "unit": "SESSION",
                "duration_minutes": 60,
                "price": 5000,
                "platform_fee_rate": "0.2000",
                "status": "ACTIVE",
                "config_json": {},
            },
        )
        assert created_sku.status_code == 201
        sku_id = created_sku.json()["id"]

        public = client.get(f"/api/v1/games/{game_id}/skus")
        assert public.status_code == 200
        assert any(item["id"] == sku_id for item in public.json())

        disabled = client.patch(
            f"/api/v1/admin/catalog/games/{game_id}",
            headers=headers,
            json={"status": "INACTIVE"},
        )
        assert disabled.status_code == 200

        public_after = client.get(f"/api/v1/games/{game_id}/skus")
        assert public_after.status_code == 404
