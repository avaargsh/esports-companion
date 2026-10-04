import uuid

from fastapi.testclient import TestClient

from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Game, PlayerProfile, PlayerSkill, ProviderOffering, ServiceSKU, User


def test_public_player_only_exposes_offerings_for_approved_skills():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        user = User(openid=f"skill-filter-player-{suffix}", nickname="Skill Filter Player")
        approved_game = Game(code=f"approved-{suffix}", name="Approved Game", status="ACTIVE", sort_order=1)
        unapproved_game = Game(code=f"unapproved-{suffix}", name="Unapproved Game", status="ACTIVE", sort_order=2)
        db.add_all([user, approved_game, unapproved_game])
        db.flush()
        approved_sku = ServiceSKU(
            game_id=approved_game.id,
            name="Approved SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate="0.2000",
            status="ACTIVE",
        )
        unapproved_sku = ServiceSKU(
            game_id=unapproved_game.id,
            name="Unapproved SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=4500,
            platform_fee_rate="0.2000",
            status="ACTIVE",
        )
        player = PlayerProfile(
            user_id=user.id,
            display_name="Skill Filter",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        db.add_all([approved_sku, unapproved_sku, player])
        db.flush()
        db.add_all([
            PlayerSkill(
                player_id=player.id,
                game_id=approved_game.id,
                rank="认证段位",
                description="已通过",
                evidence_url="https://example.com/approved.png",
                verification_status="APPROVED",
                status="ACTIVE",
            ),
            ProviderOffering(player_id=player.id, sku_id=approved_sku.id, status="ACTIVE"),
            ProviderOffering(player_id=player.id, sku_id=unapproved_sku.id, status="ACTIVE"),
        ])
        db.commit()
        player_id = str(player.id)

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/players/{player_id}")
            assert response.status_code == 200
            payload = response.json()
            assert [item["game_name"] for item in payload["skills"]] == ["Approved Game"]
            assert [item["game_name"] for item in payload["offerings"]] == ["Approved Game"]
            assert payload["available_actions"] == ["CREATE_DESIGNATED_ORDER"]
    finally:
        with SessionLocal() as db:
            player = db.get(PlayerProfile, uuid.UUID(player_id))
            if player:
                player.service_status = "OFFLINE"
            user = db.scalar(select(User).where(User.openid == f"skill-filter-player-{suffix}"))
            if user:
                user.status = "INACTIVE"
            for game in db.scalars(select(Game).where(Game.code.in_([f"approved-{suffix}", f"unapproved-{suffix}"]))):
                game.status = "DELETED"
            db.commit()
