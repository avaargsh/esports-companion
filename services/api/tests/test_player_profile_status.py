from fastapi.testclient import TestClient

from app.main import app


def test_admin_can_cancel_player_qualification_and_player_profile_returns_codes():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        player_profile_id = demo["playerProfileId"]
        admin_headers = {"X-Admin-Id": demo["adminUserId"]}
        player_headers = {"X-User-Id": player_user_id}

        listed_before = client.get("/api/v1/admin/players", headers=admin_headers)
        assert listed_before.status_code == 200
        row_before = next(item for item in listed_before.json() if item["id"] == player_profile_id)
        assert row_before["verificationStatus"] == "审核通过"
        assert row_before["verificationStatusCode"] == "APPROVED"
        assert row_before["serviceStatus"] in {"可接单", "暂停接单"}

        cancelled = client.post(
            f"/api/v1/admin/players/{player_profile_id}/cancel",
            headers=admin_headers,
            json={"reason": "测试取消资格"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["verificationStatus"] == "资格已取消"
        assert cancelled.json()["verificationStatusCode"] == "CANCELLED"
        assert cancelled.json()["serviceStatus"] == "暂停接单"
        assert cancelled.json()["serviceStatusCode"] == "OFFLINE"

        profile = client.get("/api/v1/player/profile", headers=player_headers)
        assert profile.status_code == 200
        assert profile.json()["verification_status"] == "CANCELLED"
        
        enable = client.put(
            "/api/v1/player/profile",
            headers=player_headers,
            json={"service_status": "AVAILABLE"},
        )
        assert enable.status_code == 409
        assert enable.json()["detail"] == "PLAYER_QUALIFICATION_CANCELLED"

        restored = client.post(
            f"/api/v1/admin/players/{player_profile_id}/approve",
            headers=admin_headers,
        )
        assert restored.status_code == 200
        assert restored.json()["verificationStatus"] == "审核通过"
        assert restored.json()["verificationStatusCode"] == "APPROVED"

        available = client.put(
            "/api/v1/player/profile",
            headers=player_headers,
            json={"service_status": "AVAILABLE"},
        )
        assert available.status_code == 200
        assert available.json()["service_status"] == "AVAILABLE"


def test_cancelled_player_can_reapply_for_review():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        player_profile_id = demo["playerProfileId"]
        admin_headers = {"X-Admin-Id": demo["adminUserId"]}
        player_headers = {"X-User-Id": player_user_id}

        cancelled = client.post(
            f"/api/v1/admin/players/{player_profile_id}/cancel",
            headers=admin_headers,
            json={"reason": "测试重新申请"},
        )
        assert cancelled.status_code == 200

        reapplied = client.post(
            "/api/v1/player/apply",
            headers=player_headers,
            json={"display_name": "重新申请陪玩", "bio": "重新提交资料"},
        )
        assert reapplied.status_code == 201
        payload = reapplied.json()
        assert payload["id"] == player_profile_id
        assert payload["display_name"] == "重新申请陪玩"
        assert payload["verification_status"] == "PENDING"
        assert payload["service_status"] == "OFFLINE"

        profile = client.get("/api/v1/player/profile", headers=player_headers)
        assert profile.status_code == 200
        assert profile.json()["verification_status"] == "PENDING"
