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


def test_platform_can_soft_delete_game():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        admin_id = demo["adminUserId"]
        headers = {"X-Admin-Id": admin_id}
        code = f"delete-{uuid.uuid4().hex[:8]}"

        created_game = client.post(
            "/api/v1/admin/catalog/games",
            headers=headers,
            json={
                "code": code,
                "name": "Delete Test",
                "icon_url": "http://localhost:9000/esports-images/game-icons/delete.png",
                "sort_order": 109,
            },
        )
        assert created_game.status_code == 201
        game_id = created_game.json()["id"]

        created_sku = client.post(
            "/api/v1/admin/catalog/skus",
            headers=headers,
            json={
                "game_id": game_id,
                "name": "Delete Test 1h",
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

        deleted = client.delete(f"/api/v1/admin/catalog/games/{game_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "DELETED"

        games = client.get("/api/v1/admin/catalog/games", headers=headers)
        assert games.status_code == 200
        assert all(item["id"] != game_id for item in games.json())

        skus = client.get("/api/v1/admin/catalog/skus", headers=headers)
        assert skus.status_code == 200
        assert all(item["gameId"] != game_id for item in skus.json())


def test_platform_can_upload_catalog_image(monkeypatch):
    from app.routers import admin_catalog

    class FakeStorage:
        def upload_image_bytes(self, *, filename, content, content_type):
            assert filename == "game.svg"
            assert content == b"<svg></svg>"
            assert content_type == "image/svg+xml"
            return "images/game.svg"

        def get_public_url(self, key):
            return "http://minio.local/esports-images/" + key

    monkeypatch.setattr(admin_catalog, "_storage", lambda: FakeStorage())

    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        uploaded = client.post(
            "/api/v1/admin/catalog/images",
            headers={"X-Admin-Id": demo["adminUserId"]},
            json={
                "filename": "game.svg",
                "content_type": "image/svg+xml",
                "data_base64": "PHN2Zz48L3N2Zz4=",
            },
        )
        assert uploaded.status_code == 201
        assert uploaded.json() == {
            "key": "images/game.svg",
            "url": "http://minio.local/esports-images/images/game.svg",
        }


def test_catalog_image_upload_rejects_invalid_data():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        uploaded = client.post(
            "/api/v1/admin/catalog/images",
            headers={"X-Admin-Id": demo["adminUserId"]},
            json={
                "filename": "game.txt",
                "content_type": "text/plain",
                "data_base64": "not-valid-base64",
            },
        )
        assert uploaded.status_code == 400
        assert uploaded.json()["detail"] == "INVALID_IMAGE_DATA"
