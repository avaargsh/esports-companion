import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, PlayerProfile, Settlement
from app.security import Principal, require_platform

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/players")
def list_players(
    status: str | None = Query(default=None),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    stmt = select(PlayerProfile).order_by(PlayerProfile.created_at.desc())
    if status:
        stmt = stmt.where(PlayerProfile.verification_status == status)
    players = list(db.scalars(stmt))
    return [
        {
            "id": str(player.id),
            "userId": str(player.user_id),
            "displayName": player.display_name,
            "verificationStatus": player.verification_status,
            "serviceStatus": player.service_status,
            "rating": float(player.rating),
            "orderCount": player.order_count,
        }
        for player in players
    ]


@router.post("/players/{player_id}/approve")
def approve_player(
    player_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    player = db.get(PlayerProfile, player_id)
    if not player:
        raise HTTPException(404, "PLAYER_NOT_FOUND")
    player.verification_status = "APPROVED"
    player.service_status = "OFFLINE"
    db.commit()
    return {"id": str(player.id), "verificationStatus": player.verification_status}


@router.post("/players/{player_id}/reject")
def reject_player(
    player_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    player = db.get(PlayerProfile, player_id)
    if not player:
        raise HTTPException(404, "PLAYER_NOT_FOUND")
    player.verification_status = "REJECTED"
    player.service_status = "SUSPENDED"
    db.commit()
    return {"id": str(player.id), "verificationStatus": player.verification_status}


@router.get("/orders")
def list_orders(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    orders = list(db.scalars(select(Order).order_by(Order.created_at.desc()).limit(100)))
    return [
        {
            "id": str(order.id),
            "orderNo": order.order_no,
            "userId": str(order.user_id),
            "status": order.status,
            "totalAmount": order.total_amount,
            "version": order.version,
            "createdAt": order.created_at,
        }
        for order in orders
    ]


@router.get("/settlements")
def list_settlements(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    settlements = list(
        db.scalars(select(Settlement).order_by(Settlement.created_at.desc()).limit(100))
    )
    return [
        {
            "id": str(item.id),
            "orderId": str(item.order_id),
            "playerId": str(item.player_id),
            "grossAmount": item.gross_amount,
            "playerAmount": item.player_amount,
            "platformFee": item.platform_fee,
            "status": item.status,
        }
        for item in settlements
    ]
