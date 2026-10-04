from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import OutboxEvent, PlayerSkillAuditLog


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
        assert approved.json()["verificationStatus"] == "审核通过"
        assert approved.json()["verificationStatusCode"] == "APPROVED"

        with SessionLocal() as db:
            audit = db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "AUDIT",
                    OutboxEvent.aggregate_id == f"PLAYER_SKILL:{skill_id}",
                    OutboxEvent.event_type == "AUTHORIZATION_DECISION",
                    OutboxEvent.payload_json["action"].as_string() == "PLAYER_SKILL_APPROVE",
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


def test_admin_can_detail_reject_and_revoke_player_skill():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        player_profile_id = demo["playerProfileId"]
        admin_user_id = demo["adminUserId"]
        game = demo["games"][1]

        player_headers = {"X-User-Id": player_user_id}
        admin_headers = {"X-Admin-Id": admin_user_id}

        submitted = client.put(
            f"/api/v1/player/skills/{game['id']}",
            headers=player_headers,
            json={
                "rank": "巅峰 1800",
                "description": "打野位认证",
                "evidence_url": "http://localhost:9000/esports-images/player-skills/proof.png",
            },
        )
        assert submitted.status_code == 200
        skill_id = submitted.json()["id"]

        detail = client.get(
            f"/api/v1/admin/player-skills/{skill_id}",
            headers=admin_headers,
        )
        assert detail.status_code == 200
        assert detail.json()["evidenceUrl"].endswith("proof.png")
        assert "logs" in detail.json()

        rejected = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/reject",
            headers=admin_headers,
            json={"reason": "截图段位不清晰"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["verificationStatus"] == "审核驳回"
        assert rejected.json()["verificationStatusCode"] == "REJECTED"
        assert rejected.json()["reviewNote"] == "截图段位不清晰"

        after_reject = client.get(
            f"/api/v1/admin/player-skills/{skill_id}",
            headers=admin_headers,
        ).json()
        assert after_reject["logs"][0]["action"] == "REJECT"
        assert after_reject["logs"][0]["reason"] == "截图段位不清晰"

        approved = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/approve",
            headers=admin_headers,
        )
        assert approved.status_code == 200
        assert approved.json()["verificationStatus"] == "审核通过"

        missing_reason = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/revoke",
            headers=admin_headers,
            json={"reason": ""},
        )
        assert missing_reason.status_code == 400

        revoked = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/revoke",
            headers=admin_headers,
            json={"reason": "用户申诉证明无效"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["verificationStatus"] == "已撤销"
        assert revoked.json()["verificationStatusCode"] == "REVOKED"
        assert revoked.json()["reviewNote"] == "用户申诉证明无效"

        public_after_revoke = client.get(f"/api/v1/players/{player_profile_id}")
        assert public_after_revoke.status_code == 200
        assert all(item["id"] != skill_id for item in public_after_revoke.json()["skills"])

        with SessionLocal() as db:
            logs = list(
                db.scalars(
                    select(PlayerSkillAuditLog)
                    .where(PlayerSkillAuditLog.skill_id == skill_id)
                    .order_by(PlayerSkillAuditLog.created_at)
                )
            )
            assert [item.action for item in logs][-3:] == ["REJECT", "APPROVE", "REVOKE"]
            assert str(logs[-1].operator_user_id) == admin_user_id
            revoke_audit = db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "AUDIT",
                    OutboxEvent.aggregate_id == f"PLAYER_SKILL:{skill_id}",
                    OutboxEvent.event_type == "AUTHORIZATION_DECISION",
                    OutboxEvent.payload_json["action"].as_string() == "PLAYER_SKILL_REVOKE",
                )
            )
            assert revoke_audit is not None


def test_admin_skill_rows_expose_review_and_revoke_actions():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        admin_headers = {"X-Admin-Id": demo["adminUserId"]}
        game = demo["games"][0]

        submitted = client.put(
            f"/api/v1/player/skills/{game['id']}",
            headers={"X-User-Id": player_user_id},
            json={
                "rank": "测试段位",
                "description": "动作契约",
                "evidence_url": "https://example.com/skill.png",
            },
        )
        assert submitted.status_code == 200
        skill_id = submitted.json()["id"]

        listed = client.get("/api/v1/admin/player-skills", headers=admin_headers)
        assert listed.status_code == 200
        pending = next(item for item in listed.json() if item["id"] == skill_id)
        assert pending["verificationStatus"] == "待审核"
        assert pending["verificationStatusCode"] == "PENDING"
        assert pending["availableActions"] == ["APPROVE", "REJECT"]

        approved = client.post(
            f"/api/v1/admin/player-skills/{skill_id}/approve",
            headers=admin_headers,
        )
        assert approved.status_code == 200
        assert approved.json()["availableActions"] == ["REVOKE"]
