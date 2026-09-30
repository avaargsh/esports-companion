from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import OutboxEvent


def test_player_skill_submission_review_publication_and_resubmission():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        player_profile_id = demo["playerProfileId"]
        admin_user_id = demo["adminUserId"]
        game = demo["games"][0]

        player_headers = {"X-User-Id": player_user_id}
        admin_headers = {"X-Admin-Id": admin_user_id}

        submitted = client.put(
            f"/api/v1/player/skills/{game['id']}",
            headers=player_headers,
            json={
                "rank": "王者 50 星",
                "description": "主玩辅助",
                "evidence_url": "https://example.com/proof-1.png",
            },
        )
        assert submitted.status_code == 200
        skill = submitted.json()
        assert skill["verification_status"] == "PENDING"
        skill_id = skill["id"]

        private_list = client.get(
            "/api/v1/player/skills",
            headers=player_headers,
        )
        assert private_list.status_code == 200
        assert any(item["id"] == skill_id for item in private_list.json())

        public_before = client.get(f"/api/v1/players/{player_profile_id}")
        assert public_before.status_code == 200
        assert all(item["id"] != skill_id for item in public_before.json()["skills"])

        pending = client.get(
            "/api/v1/admin/player-skills",
            params={"status": "PENDING"},
            headers=admin_headers,
        )
        assert pending.status_code == 200
        assert any(item["id"] == skill_id for item in pending.json())

        approved = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/approve",
            headers=admin_headers,
        )
        assert approved.status_code == 200
        assert approved.json()["verificationStatus"] == "APPROVED"

        with SessionLocal() as db:
            audit = db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "AUDIT",
                    OutboxEvent.aggregate_id == f"PLAYER_SKILL:{skill_id}",
                    OutboxEvent.event_type == "AUTHORIZATION_DECISION",
                )
            )
            assert audit is not None
            assert audit.payload_json["actorUserId"] == admin_user_id
            assert audit.payload_json["action"] == "PLAYER_SKILL_APPROVE"
            assert audit.payload_json["scope"] == "PLATFORM"

        public_after = client.get(f"/api/v1/players/{player_profile_id}")
        assert public_after.status_code == 200
        assert any(
            item["id"] == skill_id and item["rank"] == "王者 50 星"
            for item in public_after.json()["skills"]
        )

        filtered = client.get(
            "/api/v1/players",
            params={"game_id": game["id"], "rank": "王者 50 星"},
        )
        assert filtered.status_code == 200
        assert any(item["id"] == player_profile_id for item in filtered.json())

        resubmitted = client.put(
            f"/api/v1/player/skills/{game['id']}",
            headers=player_headers,
            json={
                "rank": "王者 60 星",
                "description": "更新段位",
                "evidence_url": "https://example.com/proof-2.png",
            },
        )
        assert resubmitted.status_code == 200
        assert resubmitted.json()["id"] == skill_id
        assert resubmitted.json()["verification_status"] == "PENDING"

        public_resubmitted = client.get(f"/api/v1/players/{player_profile_id}")
        assert public_resubmitted.status_code == 200
        assert all(item["id"] != skill_id for item in public_resubmitted.json()["skills"])
