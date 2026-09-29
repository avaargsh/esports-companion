import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, ServiceSKU
from app.schemas import GameOut, SKUOut

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/games", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)):
    return list(db.scalars(select(Game).where(Game.status == "ACTIVE").order_by(Game.sort_order)))


@router.get("/games/{game_id}/skus", response_model=list[SKUOut])
def list_skus(game_id: uuid.UUID, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "GAME_NOT_FOUND")
    return list(
        db.scalars(
            select(ServiceSKU).where(
                ServiceSKU.game_id == game_id,
                ServiceSKU.status == "ACTIVE",
            )
        )
    )
