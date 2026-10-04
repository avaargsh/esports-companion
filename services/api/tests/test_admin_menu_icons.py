from fastapi.testclient import TestClient

from app.main import app


def test_admin_menu_icons_returns_ordered_minio_urls():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        response = client.get(
            "/api/v1/admin/menu-icons",
            headers={"X-Admin-Id": demo["adminUserId"]},
        )
        assert response.status_code == 200
        rows = response.json()
        assert [item["key"] for item in rows] == [
            "dashboard",
            "orders",
            "players",
            "finance",
            "config",
        ]
        assert all(item["label"] for item in rows)
        assert all(item["iconUrl"] for item in rows)
        assert rows[0]["iconUrl"].endswith("/admin-icons/dashboard.svg")
