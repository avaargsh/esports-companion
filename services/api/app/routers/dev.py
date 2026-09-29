import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Game, PlayerProfile, ServiceSKU, User

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


def _ensure_demo_mode() -> None:
    if settings.app_env.lower() in {"prod", "production"}:
        raise HTTPException(404, "NOT_FOUND")


def _demo_records(db):
    customer = db.scalar(select(User).where(User.nickname == "Demo Customer"))
    admin = db.scalar(select(User).where(User.role == "PLATFORM"))
    players = list(
        db.execute(
            select(User, PlayerProfile)
            .join(PlayerProfile, PlayerProfile.user_id == User.id)
            .where(PlayerProfile.verification_status == "APPROVED")
            .order_by(PlayerProfile.created_at)
            .limit(10)
        )
    )
    if not customer or not admin or not players:
        raise HTTPException(503, "DEMO_DATA_NOT_SEEDED")
    return customer, admin, players


@router.get("/demo-identities")
def demo_identities():
    _ensure_demo_mode()
    with SessionLocal() as db:
        customer, admin, players = _demo_records(db)
        return {
            "customer": {
                "userId": str(customer.id),
                "nickname": customer.nickname,
            },
            "players": [
                {
                    "userId": str(user.id),
                    "playerId": str(player.id),
                    "displayName": player.display_name,
                }
                for user, player in players
            ],
            "admin": {
                "userId": str(admin.id),
                "nickname": admin.nickname,
            },
        }


@router.get("/bootstrap")
def bootstrap():
    """Backward-compatible single-call bootstrap for demos and API smoke tests."""
    _ensure_demo_mode()
    with SessionLocal() as db:
        customer, admin, players = _demo_records(db)
        player_user, player = players[0]

        games = list(
            db.scalars(
                select(Game)
                .where(Game.status == "ACTIVE")
                .order_by(Game.sort_order)
            )
        )
        skus = list(
            db.scalars(select(ServiceSKU).where(ServiceSKU.status == "ACTIVE"))
        )
        skus_by_game: dict[uuid.UUID, list[ServiceSKU]] = {}
        for sku in skus:
            skus_by_game.setdefault(sku.game_id, []).append(sku)

        return {
            "mode": "demo",
            "customerUserId": str(customer.id),
            "playerUserId": str(player_user.id),
            "playerProfileId": str(player.id),
            "adminUserId": str(admin.id),
            "games": [
                {
                    "id": str(game.id),
                    "code": game.code,
                    "name": game.name,
                    "skus": [
                        {
                            "id": str(sku.id),
                            "name": sku.name,
                            "serviceType": sku.service_type,
                            "durationMinutes": sku.duration_minutes,
                            "price": sku.price,
                        }
                        for sku in skus_by_game.get(game.id, [])
                    ],
                }
                for game in games
            ],
        }
