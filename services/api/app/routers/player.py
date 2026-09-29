import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.infrastructure import redis_client
from app.models import Order, PlayerProfile
from app.schemas import ClaimRequest, OrderOut, PlayerApply, PlayerOut, PlayerUpdate
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
        verification_status="PENDING",
        service_status="OFFLINE",
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


@router.patch("/profile", response_model=PlayerOut)
def update_profile(
    body: PlayerUpdate,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    player = get_player(db, user_id)
    if body.display_name is not None:
        player.display_name = body.display_name
    if body.bio is not None:
        player.bio = body.bio
    if body.service_status is not None:
        if body.service_status not in {"OFFLINE", "AVAILABLE"}:
            raise HTTPException(409, "INVALID_SERVICE_STATUS")
        if body.service_status == "AVAILABLE" and player.verification_status != "APPROVED":
            raise HTTPException(409, "PLAYER_NOT_APPROVED")
        player.service_status = body.service_status
    db.commit()
    db.refresh(player)
    return player


@router.get("/order-pool", response_model=list[OrderOut])
def order_pool(
    game_id: uuid.UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    try:
        ids = redis_client.zrange(
            f"order_pool:{game_id}",
            0,
            max(0, min(limit, 100) - 1),
        )
    except Exception:
        ids = []

    if ids:
        parsed_ids = [uuid.UUID(value) for value in ids]
        orders = db.scalars(
            select(Order).where(
                Order.id.in_(parsed_ids),
                Order.status == "MATCHING",
            )
        ).all()
        by_id = {str(order.id): order for order in orders}
        return [by_id[value] for value in ids if value in by_id]

    return list(
        db.scalars(
            select(Order)
            .where(
                Order.game_id == game_id,
                Order.status == "MATCHING",
            )
            .order_by(Order.created_at)
            .limit(max(1, min(limit, 100)))
        )
    )


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
        try:
            redis_client.zrem(f"order_pool:{order.game_id}", str(order.id))
        except Exception:
            pass
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


@router.get("/orders", response_model=list[OrderOut])
def player_orders(
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    player = get_player(db, user_id)
    from app.models import OrderAssignment

    return list(
        db.scalars(
            select(Order)
            .join(OrderAssignment, OrderAssignment.order_id == Order.id)
            .where(
                OrderAssignment.player_id == player.id,
                OrderAssignment.status == "ACTIVE",
            )
            .order_by(Order.created_at.desc())
            .limit(100)
        )
    )
