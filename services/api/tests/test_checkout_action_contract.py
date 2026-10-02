from fastapi.testclient import TestClient

from app.main import app


def test_public_checkout_actions_follow_catalog_and_player_availability():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        game_id = demo["games"][0]["id"]
        player_user_id = demo["playerUserId"]
        player_id = demo["playerProfileId"]

        skus = client.get(f"/api/v1/games/{game_id}/skus")
        assert skus.status_code == 200
        assert skus.json()
        assert all(
            item["available_actions"] == ["CREATE_ORDER"]
            for item in skus.json()
        )

        available = client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "AVAILABLE"},
        )
        assert available.status_code == 200

        player = client.get(f"/api/v1/players/{player_id}")
        assert player.status_code == 200
        assert player.json()["offerings"]
        assert player.json()["available_actions"] == [
            "CREATE_DESIGNATED_ORDER"
        ]

        offline = client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "OFFLINE"},
        )
        assert offline.status_code == 200

        player = client.get(f"/api/v1/players/{player_id}")
        assert player.status_code == 200
        assert player.json()["available_actions"] == []
