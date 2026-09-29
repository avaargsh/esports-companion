import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Game, PlayerProfile, ServiceSKU, User

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


@router.get("/bootstrap")
def bootstrap():
    if settings.app_env.lower() in {"prod", "production"}:
        raise HTTPException(404, "NOT_FOUND")

    with SessionLocal() as db:
        customer = db.scalar(select(User).where(User.nickname == "Demo Customer"))
        admin = db.scalar(select(User).where(User.role == "PLATFORM"))
        player = db.scalar(
            select(PlayerProfile)
            .where(PlayerProfile.verification_status == "APPROVED")
            .order_by(PlayerProfile.created_at)
            .limit(1)
        )
        if not customer or not admin or not player:
            raise HTTPException(503, "DEMO_DATA_NOT_SEEDED")

        player_user = db.get(User, player.user_id)
        games = list(
            db.scalars(
                select(Game)
                .where(Game.status == "ACTIVE")
                .order_by(Game.sort_order)
            )
        )
        skus = list(
            db.scalars(
                select(ServiceSKU).where(ServiceSKU.status == "ACTIVE")
            )
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
