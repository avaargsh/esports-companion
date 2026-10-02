import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.infrastructure import redis_client
from app.models import Game, Order, OrderAssignment, PlayerProfile, PlayerSkill, ProviderOffering
from app.schemas import (
    ClaimRequest,
    OrderOut,
    PlayerApply,
    PlayerOut,
    PlayerPoolOrderOut,
    PlayerSkillOut,
    PlayerSkillUpsert,
    PlayerUpdate,
)
from app.services.dispatch_service import (
    AssignmentNotFound,
    DispatchService,
    OrderAlreadyClaimed,
    PlayerNotEligible,
)
from app.services.order_service import OrderNotFound, OrderService
from app.security import Principal, current_user_id, require_player

router = APIRouter(prefix="/api/v1/player", tags=["player"])


def _player_available_actions(player: PlayerProfile) -> list[str]:
    if player.verification_status != "APPROVED":
        return []
    if player.service_status == "AVAILABLE":
        return ["GO_OFFLINE"]
    return ["GO_AVAILABLE"]


def _player_out(player: PlayerProfile) -> dict:
    payload = PlayerOut.model_validate(player).model_dump()
    payload["available_actions"] = _player_available_actions(player)
    return payload


def _pool_order_out(order: Order, *, can_claim: bool) -> dict:
    payload = OrderOut.model_validate(order).model_dump()
    payload["available_actions"] = ["CLAIM_ORDER"] if can_claim else []
    return payload


def get_player(db: Session, user_id: uuid.UUID) -> PlayerProfile:
    player = db.scalar(select(PlayerProfile).where(PlayerProfile.user_id == user_id))
    if not player:
        raise HTTPException(404, "PLAYER_PROFILE_NOT_FOUND")
    return player


@router.post("/apply", response_model=PlayerOut, status_code=201)
def apply(
    body: PlayerApply,
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(PlayerProfile).where(PlayerProfile.user_id == user_id))
    if existing:
        return _player_out(existing)
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
    return _player_out(player)


@router.get("/profile", response_model=PlayerOut)
def profile(
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    return _player_out(get_player(db, user_id))


@router.patch("/profile", response_model=PlayerOut)
@router.put("/profile", response_model=PlayerOut)
def update_profile(
    body: PlayerUpdate,
    user_id: uuid.UUID = Depends(current_user_id),
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
    return _player_out(player)


@router.get("/skills", response_model=list[PlayerSkillOut])
def list_skills(
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player = get_player(db, principal.user_id)
    return list(
        db.scalars(
            select(PlayerSkill)
            .where(PlayerSkill.player_id == player.id)
            .order_by(PlayerSkill.created_at)
        )
    )


@router.put("/skills/{game_id}", response_model=PlayerSkillOut)
def upsert_skill(
    game_id: uuid.UUID,
    body: PlayerSkillUpsert,
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player = get_player(db, principal.user_id)
    game = db.get(Game, game_id)
    if not game or game.status != "ACTIVE":
        raise HTTPException(404, "GAME_NOT_FOUND")

    skill = db.scalar(
        select(PlayerSkill).where(
            PlayerSkill.player_id == player.id,
            PlayerSkill.game_id == game_id,
        )
    )
    if not skill:
        skill = PlayerSkill(
            player_id=player.id,
            game_id=game_id,
        )
        db.add(skill)

    skill.rank = body.rank.strip()
    skill.description = body.description.strip()
    skill.evidence_url = body.evidence_url.strip()
    skill.verification_status = "PENDING"
    skill.review_note = ""
    skill.status = "ACTIVE"
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/order-pool", response_model=list[PlayerPoolOrderOut])
def order_pool(
    game_id: uuid.UUID,
    limit: int = 20,
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player_profile = get_player(db, principal.user_id)
    page_limit = max(1, min(limit, 100))
    try:
        ids = redis_client.zrange(
            f"order_pool:{game_id}",
            0,
            page_limit - 1,
        )
    except Exception:
        ids = []

    result: list[Order] = []
    parsed_ids: list[uuid.UUID] = []
    if ids:
        parsed_ids = [uuid.UUID(value) for value in ids]
        redis_orders = db.scalars(
            select(Order)
            .join(
                ProviderOffering,
                ProviderOffering.sku_id == Order.sku_id,
            )
            .where(
                Order.id.in_(parsed_ids),
                Order.game_id == game_id,
                Order.status == "MATCHING",
                ProviderOffering.player_id == player_profile.id,
                ProviderOffering.status == "ACTIVE",
            )
        ).all()
        by_id = {str(order.id): order for order in redis_orders}
        result.extend(by_id[value] for value in ids if value in by_id)

    remaining = page_limit - len(result)
    if remaining > 0:
        fallback = (
            select(Order)
            .join(
                ProviderOffering,
                ProviderOffering.sku_id == Order.sku_id,
            )
            .where(
                Order.game_id == game_id,
                Order.status == "MATCHING",
                ProviderOffering.player_id == player_profile.id,
                ProviderOffering.status == "ACTIVE",
            )
            .order_by(Order.created_at)
            .limit(remaining)
        )
        if parsed_ids:
            fallback = fallback.where(Order.id.not_in(parsed_ids))
        result.extend(db.scalars(fallback).all())

    can_claim = (
        player_profile.verification_status == "APPROVED"
        and player_profile.service_status == "AVAILABLE"
    )
    return [_pool_order_out(order, can_claim=can_claim) for order in result]


@router.get("/orders", response_model=list[OrderOut])
def player_orders(
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    user_id = principal.user_id
    player = get_player(db, user_id)
    return list(
        db.scalars(
            select(Order)
            .join(OrderAssignment, OrderAssignment.order_id == Order.id)
            .where(
                OrderAssignment.player_id == player.id,
                OrderAssignment.status == "ACTIVE",
            )
            .order_by(Order.created_at.desc())
        )
    )


@router.post("/orders/{order_id}/claim", response_model=OrderOut)
def claim(
    order_id: uuid.UUID,
    body: ClaimRequest,
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player = get_player(db, principal.user_id)
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
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player = get_player(db, principal.user_id)
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
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    player = get_player(db, principal.user_id)
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
