import uuid

from fastapi.testclient import TestClient

from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Game, PlayerProfile, PlayerSkill, User


def test_public_catalog_includes_all_active_games():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        ops_game = Game(code=f"ops-game-{suffix}", name="Ops Game", status="ACTIVE", sort_order=0)
        real_game = Game(code=f"live-game-{suffix}", name="真实游戏", status="ACTIVE", sort_order=1)
        inactive_game = Game(code=f"inactive-game-{suffix}", name="停用游戏", status="INACTIVE", sort_order=2)
        db.add_all([ops_game, real_game, inactive_game])
        db.commit()
        ops_id = str(ops_game.id)
        real_id = str(real_game.id)
        inactive_id = str(inactive_game.id)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/games")

        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert ops_id in ids
        assert real_id in ids
        assert inactive_id not in ids
    finally:
        with SessionLocal() as db:
            for game in db.scalars(select(Game).where(Game.code.in_([f"ops-game-{suffix}", f"live-game-{suffix}", f"inactive-game-{suffix}"]))):
                game.status = "DELETED"
            db.commit()


def test_public_marketplace_includes_approved_available_players_with_skills():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        skill_user = User(openid=f"skill-filter-player-{suffix}", nickname="Skill Filter Player")
        real_user = User(openid=f"obRealPlayer{suffix}", nickname="真实陪玩")
        game = Game(code=f"live-market-{suffix}", name="真实游戏", status="ACTIVE", sort_order=1)
        db.add_all([skill_user, real_user, game])
        db.flush()
        skill_player = PlayerProfile(
            user_id=skill_user.id,
            display_name="Skill Filter",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        real_player = PlayerProfile(
            user_id=real_user.id,
            display_name="真实陪玩",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        db.add_all([skill_player, real_player])
        db.flush()
        for player in (skill_player, real_player):
            db.add(PlayerSkill(
                player_id=player.id,
                game_id=game.id,
                rank="认证段位",
                description="已通过",
                evidence_url="https://example.com/evidence.png",
                verification_status="APPROVED",
                status="ACTIVE",
            ))
        db.commit()
        skill_player_id = str(skill_player.id)
        real_player_id = str(real_player.id)

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/players?limit=50")

        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert skill_player_id in ids
        assert real_player_id in ids
    finally:
        with SessionLocal() as db:
            for user in db.scalars(select(User).where(User.openid.in_([f"skill-filter-player-{suffix}", f"obRealPlayer{suffix}"]))):
                user.status = "INACTIVE"
            for game in db.scalars(select(Game).where(Game.code == f"live-market-{suffix}")):
                game.status = "DELETED"
            db.commit()
