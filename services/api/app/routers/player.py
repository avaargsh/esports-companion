import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.infrastructure import redis_client
from app.models import Order, PlayerProfile
from app.schemas import ClaimRequest, OrderOut, PlayerApply, PlayerOut
from app.services.dispatch_service import (
    AssignmentNotFound,
    DispatchService,
    OrderAlreadyClaimed,
    PlayerNotEligible,
)
from app.services.order_service import OrderNotFound, OrderService

router = APIRouter(prefix="/api/v1/player", tags=["player"])


def demo_user_id(x_user_id: uuid.UUID = Header(alias="X-User-Id")) -> uuid.UUID:
    return x_user_id


def get_player(db: Session, user_id: uuid.UUID) -> PlayerProfile:
    player = db.scalar(select(PlayerProfile).where(PlayerProfile.user_id == user_id))
    if not player:
        raise HTTPException(404, "PLAYER_PROFILE_NOT_FOUND")
    return player


@router.post("/apply", response_model=PlayerOut, status_code=201)
def apply(
    body: PlayerApply,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(PlayerProfile).where(PlayerProfile.user_id == user_id))
    if existing:
        return existing
    player = PlayerProfile(
        user_id=user_id,
        display_name=body.display_name,
        bio=body.bio,
        verification_status="APPROVED",
        service_status="AVAILABLE",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("/profile", response_model=PlayerOut)
def profile(
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    return get_player(db, user_id)


@router.get("/order-pool", response_model=list[OrderOut])
def order_pool(
    game_id: uuid.UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    ids = redis_client.zrange(f"order_pool:{game_id}", 0, max(0, min(limit, 100) - 1))
    if not ids:
        return []
    parsed_ids = [uuid.UUID(value) for value in ids]
    orders = db.scalars(
        select(Order).where(Order.id.in_(parsed_ids), Order.status == "MATCHING")
    ).all()
    by_id = {str(order.id): order for order in orders}
    return [by_id[value] for value in ids if value in by_id]


@router.post("/orders/{order_id}/claim", response_model=OrderOut)
def claim(
    order_id: uuid.UUID,
    body: ClaimRequest,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    player = get_player(db, user_id)
    try:
        order = DispatchService.claim(
            db,
            order_id=order_id,
            player_id=player.id,
            expected_version=body.expected_version,
        )
        redis_client.zrem(f"order_pool:{order.game_id}", str(order.id))
        return order
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OrderAlreadyClaimed, PlayerNotEligible) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/orders/{order_id}/start", response_model=OrderOut)
def start(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    player = get_player(db, user_id)
    try:
        order = OrderService.get(db, order_id)
        return DispatchService.start(db, order=order, player_id=player.id)
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except AssignmentNotFound as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/orders/{order_id}/finish", response_model=OrderOut)
def finish(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    player = get_player(db, user_id)
    try:
        order = OrderService.get(db, order_id)
        return DispatchService.finish(db, order=order, player_id=player.id)
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except AssignmentNotFound as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
