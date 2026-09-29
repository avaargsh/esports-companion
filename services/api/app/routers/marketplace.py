import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Game,
    PlayerProfile,
    ProviderOffering,
    Review,
    ServiceSKU,
    User,
)
from app.schemas import PublicOfferingOut, PublicPlayerOut, PublicReviewOut

router = APIRouter(prefix="/api/v1/players", tags=["marketplace"])


def _offerings_for(db: Session, player_id: uuid.UUID) -> list[PublicOfferingOut]:
    rows = db.execute(
        select(ProviderOffering, ServiceSKU, Game)
        .join(ServiceSKU, ServiceSKU.id == ProviderOffering.sku_id)
        .join(Game, Game.id == ServiceSKU.game_id)
        .where(
            ProviderOffering.player_id == player_id,
            ProviderOffering.status == "ACTIVE",
            ServiceSKU.status == "ACTIVE",
            Game.status == "ACTIVE",
        )
        .order_by(Game.sort_order, ServiceSKU.price)
    ).all()
    return [
        PublicOfferingOut(
            id=offering.id,
            sku_id=sku.id,
            game_id=game.id,
            game_name=game.name,
            sku_name=sku.name,
            service_type=sku.service_type,
            duration_minutes=sku.duration_minutes,
            price=offering.price_override if offering.price_override is not None else sku.price,
            description=offering.description,
        )
        for offering, sku, game in rows
    ]


def _rating(db: Session, player_id: uuid.UUID) -> tuple[float, int]:
    avg_rating, review_count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.player_id == player_id
        )
    ).one()
    return float(avg_rating or 0), int(review_count or 0)


def _public_player(
    db: Session,
    player: PlayerProfile,
    *,
    include_reviews: bool = False,
) -> PublicPlayerOut:
    user = db.get(User, player.user_id)
    rating, review_count = _rating(db, player.id)
    reviews: list[PublicReviewOut] = []
    if include_reviews:
        reviews = [
            PublicReviewOut(id=item.id, rating=item.rating, content=item.content)
            for item in db.scalars(
                select(Review)
                .where(Review.player_id == player.id)
                .order_by(Review.created_at.desc())
                .limit(20)
            )
        ]
    return PublicPlayerOut(
        id=player.id,
        display_name=player.display_name,
        avatar_url=user.avatar_url if user else None,
        bio=player.bio,
        gender=player.gender,
        service_status=player.service_status,
        rating=rating,
        review_count=review_count,
        order_count=player.order_count,
        offerings=_offerings_for(db, player.id),
        reviews=reviews,
    )


@router.get("", response_model=list[PublicPlayerOut])
def list_players(
    game_id: uuid.UUID | None = None,
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    stmt = (
        select(PlayerProfile)
        .where(
            PlayerProfile.verification_status == "APPROVED",
            PlayerProfile.service_status == "AVAILABLE",
        )
        .order_by(PlayerProfile.rating.desc(), PlayerProfile.created_at)
        .limit(limit)
    )
    players = list(db.scalars(stmt))
    result = []
    for player in players:
        item = _public_player(db, player)
        if game_id and not any(offering.game_id == game_id for offering in item.offerings):
            continue
        if item.offerings:
            result.append(item)
    return result


@router.get("/{player_id}", response_model=PublicPlayerOut)
def get_player(player_id: uuid.UUID, db: Session = Depends(get_db)):
    player = db.get(PlayerProfile, player_id)
    if not player or player.verification_status != "APPROVED":
        raise HTTPException(404, "PLAYER_NOT_FOUND")
    return _public_player(db, player, include_reviews=True)
