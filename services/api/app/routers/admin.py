import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Game, Order, PlayerProfile, PlayerSkill, Settlement, Withdrawal
from app.security import Principal, require_platform
from app.services.withdrawal_service import WithdrawalService

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


@router.get("/player-skills")
def list_player_skills(
    status: str | None = Query(default=None),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    stmt = (
        select(PlayerSkill, PlayerProfile, Game)
        .join(PlayerProfile, PlayerProfile.id == PlayerSkill.player_id)
        .join(Game, Game.id == PlayerSkill.game_id)
        .order_by(PlayerSkill.updated_at.desc())
    )
    if status:
        stmt = stmt.where(PlayerSkill.verification_status == status.upper())

    return [
        {
            "id": str(skill.id),
            "playerId": str(player.id),
            "playerName": player.display_name,
            "gameId": str(game.id),
            "gameName": game.name,
            "rank": skill.rank,
            "description": skill.description,
            "evidenceUrl": skill.evidence_url,
            "verificationStatus": skill.verification_status,
            "reviewNote": skill.review_note,
            "updatedAt": skill.updated_at,
        }
        for skill, player, game in db.execute(stmt)
    ]


@router.post("/player-skills/{skill_id}/approve")
def approve_player_skill(
    skill_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    skill = db.get(PlayerSkill, skill_id)
    if not skill:
        raise HTTPException(404, "PLAYER_SKILL_NOT_FOUND")
    skill.verification_status = "APPROVED"
    skill.review_note = ""
    db.commit()
    return {"id": str(skill.id), "verificationStatus": skill.verification_status}


@router.post("/player-skills/{skill_id}/reject")
def reject_player_skill(
    skill_id: uuid.UUID,
    note: str = Query(default="EVIDENCE_INSUFFICIENT", max_length=500),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    skill = db.get(PlayerSkill, skill_id)
    if not skill:
        raise HTTPException(404, "PLAYER_SKILL_NOT_FOUND")
    skill.verification_status = "REJECTED"
    skill.review_note = note.strip()
    db.commit()
    return {
        "id": str(skill.id),
        "verificationStatus": skill.verification_status,
        "reviewNote": skill.review_note,
    }


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



@router.get("/withdrawals")
def list_withdrawals(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    rows = list(
        db.scalars(
            select(Withdrawal)
            .order_by(Withdrawal.created_at.desc())
            .limit(100)
        )
    )
    return [
        {
            "id": str(item.id),
            "userId": str(item.user_id),
            "amount": item.amount,
            "status": item.status,
            "provider": item.provider,
            "providerTxnId": item.provider_txn_id,
            "failureReason": item.failure_reason,
            "createdAt": item.created_at,
        }
        for item in rows
    ]


@router.post("/withdrawals/{withdrawal_id}/complete")
def complete_withdrawal(
    withdrawal_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        item = WithdrawalService.complete(
            db,
            withdrawal_id=withdrawal_id,
            provider_txn_id=f"manual:{withdrawal_id}",
        )
        return {"id": str(item.id), "status": item.status}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/withdrawals/{withdrawal_id}/reject")
def reject_withdrawal(
    withdrawal_id: uuid.UUID,
    reason: str = Query(default="REJECTED_BY_PLATFORM", max_length=256),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        item = WithdrawalService.reject(
            db,
            withdrawal_id=withdrawal_id,
            reason=reason,
        )
        return {"id": str(item.id), "status": item.status}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
