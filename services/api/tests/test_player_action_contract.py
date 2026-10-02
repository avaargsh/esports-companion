from fastapi.testclient import TestClient

from app.main import app


def test_player_action_contract_controls_availability_and_claim_affordance():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()

        customer_id = demo["customerUserId"]
        player_user_id = demo["playerUserId"]
        game = demo["games"][0]
        game_id = game["id"]
        sku_id = game["skus"][0]["id"]

        offline = client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "OFFLINE"},
        )
        assert offline.status_code == 200
        assert offline.json()["available_actions"] == ["GO_AVAILABLE"]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku_id, "quantity": 1, "remark": "player action contract"},
        )
        assert created.status_code == 201
        order_id = created.json()["id"]

        paid = client.post(
            f"/api/v1/orders/{order_id}/mock-pay",
            headers={
                "X-User-Id": customer_id,
                "Idempotency-Key": f"player-actions-pay-{order_id}",
            },
        )
        assert paid.status_code == 200
        assert paid.json()["status"] == "MATCHING"

        offline_pool = client.get(
            f"/api/v1/player/order-pool?game_id={game_id}",
            headers={"X-User-Id": player_user_id},
        )
        assert offline_pool.status_code == 200
        pool_order = next(
            item for item in offline_pool.json()
            if item["id"] == order_id
        )
        assert pool_order["available_actions"] == []

        available = client.put(
            "/api/v1/player/profile",
            headers={"X-User-Id": player_user_id},
            json={"service_status": "AVAILABLE"},
        )
        assert available.status_code == 200
        assert available.json()["available_actions"] == ["GO_OFFLINE"]

        available_pool = client.get(
            f"/api/v1/player/order-pool?game_id={game_id}",
            headers={"X-User-Id": player_user_id},
        )
        assert available_pool.status_code == 200
        pool_order = next(
            item for item in available_pool.json()
            if item["id"] == order_id
        )
        assert pool_order["available_actions"] == ["CLAIM_ORDER"]


def test_player_needs_approved_skill_before_enabling_service_or_offering():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["customerUserId"]
        admin_headers = {"X-Admin-Id": demo["adminUserId"]}
        player_headers = {"X-User-Id": player_user_id}
        game = demo["games"][0]
        sku_id = game["skus"][0]["id"]

        applied = client.post(
            "/api/v1/player/apply",
            headers=player_headers,
            json={"display_name": "无技能陪玩", "bio": "已通过但无技能"},
        )
        assert applied.status_code == 201
        player_id = applied.json()["id"]

        approved = client.post(
            f"/api/v1/admin/players/{player_id}/approve",
            headers=admin_headers,
        )
        assert approved.status_code == 200

        enable = client.put(
            "/api/v1/player/profile",
            headers=player_headers,
            json={"service_status": "AVAILABLE"},
        )
        assert enable.status_code == 409
        assert enable.json()["detail"] == "PLAYER_SKILL_REQUIRED"

        offering = client.put(
            f"/api/v1/player/offerings/{sku_id}",
            headers=player_headers,
            json={"price_override": None, "description": "", "status": "ACTIVE"},
        )
        assert offering.status_code == 409
        assert offering.json()["detail"] == "PLAYER_SKILL_REQUIRED"

        submitted = client.put(
            f"/api/v1/player/skills/{game['id']}",
            headers=player_headers,
            json={
                "rank": "认证段位",
                "description": "补齐认证",
                "evidence_url": "https://example.com/approved.png",
            },
        )
        assert submitted.status_code == 200
        skill_id = submitted.json()["id"]
        reviewed = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/approve",
            headers=admin_headers,
        )
        assert reviewed.status_code == 200

        offering_after_skill = client.put(
            f"/api/v1/player/offerings/{sku_id}",
            headers=player_headers,
            json={"price_override": None, "description": "", "status": "ACTIVE"},
        )
        assert offering_after_skill.status_code == 200

        enable_after_skill = client.put(
            "/api/v1/player/profile",
            headers=player_headers,
            json={"service_status": "AVAILABLE"},
        )
        assert enable_after_skill.status_code == 200
