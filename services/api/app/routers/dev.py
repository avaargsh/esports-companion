from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import PlayerProfile, User

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


@router.get("/demo-identities")
def demo_identities():
    if settings.app_env == "prod":
        raise HTTPException(404, "NOT_FOUND")

    with SessionLocal() as db:
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
        if not customer:
            raise HTTPException(409, "RUN_SEED_FIRST")

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
            "admin": (
                {
                    "userId": str(admin.id),
                    "nickname": admin.nickname,
                }
                if admin
                else None
            ),
        }
