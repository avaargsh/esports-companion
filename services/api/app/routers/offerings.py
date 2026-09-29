import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PlayerProfile, ProviderOffering, ServiceSKU
from app.schemas import ProviderOfferingOut, ProviderOfferingUpsert
from app.security import Principal, require_player

router = APIRouter(prefix="/api/v1/player/offerings", tags=["player-offerings"])


def _player(db: Session, user_id: uuid.UUID) -> PlayerProfile:
    player = db.scalar(
        select(PlayerProfile).where(PlayerProfile.user_id == user_id)
    )
    if not player:
        raise HTTPException(404, "PLAYER_PROFILE_NOT_FOUND")
    return player


@router.get("", response_model=list[ProviderOfferingOut])
def list_offerings(
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player = _player(db, principal.user_id)
    return list(
        db.scalars(
            select(ProviderOffering)
            .where(ProviderOffering.player_id == player.id)
            .order_by(ProviderOffering.created_at)
        )
    )


@router.put("/{sku_id}", response_model=ProviderOfferingOut)
def upsert_offering(
    sku_id: uuid.UUID,
    body: ProviderOfferingUpsert,
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    status = body.status.upper()
    if status not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(409, "INVALID_OFFERING_STATUS")

    player = _player(db, principal.user_id)
    sku = db.get(ServiceSKU, sku_id)
    if not sku:
        raise HTTPException(404, "SKU_NOT_FOUND")

    offering = db.scalar(
        select(ProviderOffering).where(
            ProviderOffering.player_id == player.id,
            ProviderOffering.sku_id == sku.id,
        )
    )
    if not offering:
        offering = ProviderOffering(
            player_id=player.id,
            sku_id=sku.id,
        )
        db.add(offering)

    offering.price_override = body.price_override
    offering.description = body.description
    offering.status = status
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "OFFERING_ALREADY_EXISTS") from exc
    db.refresh(offering)
    return offering
