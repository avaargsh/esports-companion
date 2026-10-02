import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AdminMenuIcon,
    Game,
    LedgerEntry,
    Order,
    PlayerProfile,
    PlayerSkill,
    PlayerSkillAuditLog,
    Settlement,
    Wallet,
    Withdrawal,
)
from app.schemas import WithdrawalComplete
from app.security import Principal, require_platform
from app.services.authorization_audit import AuthorizationAudit
from app.services.operations_queue_service import build_operations_queue
from app.services.resource_authorization_policy import ResourceAuthorizationPolicy
from app.services.withdrawal_service import WithdrawalService
from app.status_labels import (
    COMMON_STATUS_TEXT,
    PLAYER_SKILL_STATUS_TEXT,
    PLAYER_VERIFICATION_STATUS_TEXT,
    SERVICE_STATUS_TEXT,
    status_text,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class PlayerSkillDecisionBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)



@router.get("/menu-icons")
def list_menu_icons(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    rows = list(
        db.scalars(
            select(AdminMenuIcon)
            .where(AdminMenuIcon.status == "ACTIVE")
            .order_by(AdminMenuIcon.sort_order, AdminMenuIcon.created_at)
        )
    )
    return [
        {
            "key": item.menu_key,
            "label": item.label,
            "iconUrl": item.icon_url,
            "sortOrder": item.sort_order,
        }
        for item in rows
    ]


def _platform_decision(
    principal: Principal,
    request: Request,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
):
    return ResourceAuthorizationPolicy.require_platform(
        actor_user_id=principal.user_id,
        actor_roles=principal.roles,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        session_id=principal.session_id,
        request_id=getattr(request.state, "request_id", None),
        business_evidence_ref=f"{resource_type}:{resource_id}",
    )


@router.get("/operations/queue")
def operations_queue(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return build_operations_queue(db)


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
            "verificationStatus": status_text(
                player.verification_status, PLAYER_VERIFICATION_STATUS_TEXT
            ),
            "verificationStatusCode": player.verification_status,
            "serviceStatus": status_text(player.service_status, SERVICE_STATUS_TEXT),
            "serviceStatusCode": player.service_status,
            "rating": float(player.rating),
            "orderCount": player.order_count,
        }
        for player in players
    ]


@router.post("/players/{player_id}/approve")
def approve_player(
    player_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    player = db.get(PlayerProfile, player_id)
    if not player:
        raise HTTPException(404, "PLAYER_NOT_FOUND")
    decision = _platform_decision(
        principal,
        request,
        action="PLAYER_APPROVE",
        resource_type="PLAYER_PROFILE",
        resource_id=str(player.id),
    )
    player.verification_status = "APPROVED"
    player.service_status = "OFFLINE"
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    return {
        "id": str(player.id),
        "verificationStatus": status_text(
                player.verification_status, PLAYER_VERIFICATION_STATUS_TEXT
            ),
            "verificationStatusCode": player.verification_status,
        "serviceStatus": status_text(player.service_status, SERVICE_STATUS_TEXT),
            "serviceStatusCode": player.service_status,
    }


@router.post("/players/{player_id}/reject")
def reject_player(
    player_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    player = db.get(PlayerProfile, player_id)
    if not player:
        raise HTTPException(404, "PLAYER_NOT_FOUND")
    decision = _platform_decision(
        principal,
        request,
        action="PLAYER_REJECT",
        resource_type="PLAYER_PROFILE",
        resource_id=str(player.id),
    )
    player.verification_status = "REJECTED"
    player.service_status = "SUSPENDED"
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    return {
        "id": str(player.id),
        "verificationStatus": status_text(
                player.verification_status, PLAYER_VERIFICATION_STATUS_TEXT
            ),
            "verificationStatusCode": player.verification_status,
        "serviceStatus": status_text(player.service_status, SERVICE_STATUS_TEXT),
            "serviceStatusCode": player.service_status,
    }


@router.post("/players/{player_id}/cancel")
def cancel_player_qualification(
    player_id: uuid.UUID,
    request: Request,
    body: PlayerSkillDecisionBody | None = None,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    player = db.get(PlayerProfile, player_id)
    if not player:
        raise HTTPException(404, "PLAYER_NOT_FOUND")
    if player.verification_status != "APPROVED":
        raise HTTPException(409, "PLAYER_NOT_APPROVED")
    reason = ((body.reason if body else None) or "资格已取消").strip()
    decision = _platform_decision(
        principal,
        request,
        action="PLAYER_CANCEL",
        resource_type="PLAYER_PROFILE",
        resource_id=str(player.id),
    )
    player.verification_status = "CANCELLED"
    player.service_status = "OFFLINE"
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    return {
        "id": str(player.id),
        "verificationStatus": status_text(
                player.verification_status, PLAYER_VERIFICATION_STATUS_TEXT
            ),
            "verificationStatusCode": player.verification_status,
        "serviceStatus": status_text(player.service_status, SERVICE_STATUS_TEXT),
            "serviceStatusCode": player.service_status,
        "reason": reason,
    }


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
        _player_skill_payload(skill, player, game)
        for skill, player, game in db.execute(stmt)
    ]


@router.get("/player-skills/{skill_id}")
def get_player_skill_detail(
    skill_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    skill, player, game = _get_player_skill_bundle(db, skill_id)
    logs = list(
        db.scalars(
            select(PlayerSkillAuditLog)
            .where(PlayerSkillAuditLog.skill_id == skill_id)
            .order_by(PlayerSkillAuditLog.created_at.desc())
        )
    )
    return _player_skill_payload(skill, player, game, logs=logs)


@router.post("/player-skills/{skill_id}/approve")
def approve_player_skill(
    skill_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    skill, player, game = _get_player_skill_bundle(db, skill_id)
    previous_status = skill.verification_status
    decision = _platform_decision(
        principal,
        request,
        action="PLAYER_SKILL_APPROVE",
        resource_type="PLAYER_SKILL",
        resource_id=str(skill.id),
    )
    skill.verification_status = "APPROVED"
    skill.review_note = ""
    _record_player_skill_log(
        db,
        skill=skill,
        principal=principal,
        action="APPROVE",
        from_status=previous_status,
        to_status=skill.verification_status,
        reason="",
    )
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    db.refresh(skill)
    return _player_skill_payload(skill, player, game)


@router.post("/player-skills/{skill_id}/reject")
def reject_player_skill(
    skill_id: uuid.UUID,
    request: Request,
    body: PlayerSkillDecisionBody | None = None,
    note: str | None = Query(default=None, max_length=500),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    skill, player, game = _get_player_skill_bundle(db, skill_id)
    previous_status = skill.verification_status
    reason = ((body.reason if body else None) or note or "EVIDENCE_INSUFFICIENT").strip()
    if not reason:
        raise HTTPException(400, "PLAYER_SKILL_REJECT_REASON_REQUIRED")
    decision = _platform_decision(
        principal,
        request,
        action="PLAYER_SKILL_REJECT",
        resource_type="PLAYER_SKILL",
        resource_id=str(skill.id),
    )
    skill.verification_status = "REJECTED"
    skill.review_note = reason
    _record_player_skill_log(
        db,
        skill=skill,
        principal=principal,
        action="REJECT",
        from_status=previous_status,
        to_status=skill.verification_status,
        reason=reason,
    )
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    db.refresh(skill)
    return _player_skill_payload(skill, player, game)


@router.post("/player-skills/{skill_id}/revoke")
def revoke_player_skill(
    skill_id: uuid.UUID,
    request: Request,
    body: PlayerSkillDecisionBody,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    skill, player, game = _get_player_skill_bundle(db, skill_id)
    if skill.verification_status != "APPROVED":
        raise HTTPException(409, "PLAYER_SKILL_NOT_APPROVED")
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(400, "PLAYER_SKILL_REVOKE_REASON_REQUIRED")

    previous_status = skill.verification_status
    decision = _platform_decision(
        principal,
        request,
        action="PLAYER_SKILL_REVOKE",
        resource_type="PLAYER_SKILL",
        resource_id=str(skill.id),
    )
    skill.verification_status = "REVOKED"
    skill.review_note = reason
    _record_player_skill_log(
        db,
        skill=skill,
        principal=principal,
        action="REVOKE",
        from_status=previous_status,
        to_status=skill.verification_status,
        reason=reason,
    )
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    db.refresh(skill)
    return _player_skill_payload(skill, player, game)


def _get_player_skill_bundle(db: Session, skill_id: uuid.UUID):
    row = db.execute(
        select(PlayerSkill, PlayerProfile, Game)
        .join(PlayerProfile, PlayerProfile.id == PlayerSkill.player_id)
        .join(Game, Game.id == PlayerSkill.game_id)
        .where(PlayerSkill.id == skill_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "PLAYER_SKILL_NOT_FOUND")
    return row


def _player_skill_payload(
    skill: PlayerSkill,
    player: PlayerProfile,
    game: Game,
    *,
    logs: list[PlayerSkillAuditLog] | None = None,
):
    payload = {
        "id": str(skill.id),
        "playerId": str(player.id),
        "playerName": player.display_name,
        "gameId": str(game.id),
        "gameName": game.name,
        "rank": skill.rank,
        "description": skill.description,
        "evidenceUrl": skill.evidence_url,
        "verificationStatus": status_text(
            skill.verification_status, PLAYER_SKILL_STATUS_TEXT
        ),
        "verificationStatusCode": skill.verification_status,
        "reviewNote": skill.review_note,
        "createdAt": skill.created_at,
        "updatedAt": skill.updated_at,
    }
    if logs is not None:
        payload["logs"] = [
            {
                "id": str(item.id),
                "action": item.action,
                "fromStatus": status_text(item.from_status, PLAYER_SKILL_STATUS_TEXT),
                "fromStatusCode": item.from_status,
                "toStatus": status_text(item.to_status, PLAYER_SKILL_STATUS_TEXT),
                "toStatusCode": item.to_status,
                "reason": item.reason,
                "operatorUserId": str(item.operator_user_id),
                "createdAt": item.created_at,
            }
            for item in logs
        ]
    return payload


def _record_player_skill_log(
    db: Session,
    *,
    skill: PlayerSkill,
    principal: Principal,
    action: str,
    from_status: str,
    to_status: str,
    reason: str,
):
    db.add(
        PlayerSkillAuditLog(
            skill_id=skill.id,
            operator_user_id=principal.user_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
        )
    )


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
            "status": order.status_text,
            "statusCode": order.status,
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
            "status": item.status_text,
            "statusCode": item.status,
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
            "status": item.status_text,
            "statusCode": item.status,
            "provider": item.provider,
            "providerTxnId": item.provider_txn_id,
            "failureReason": item.failure_reason,
            "createdAt": item.created_at,
        }
        for item in rows
    ]


@router.get("/withdrawals/{withdrawal_id}/evidence")
def withdrawal_evidence(
    withdrawal_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    item = db.get(Withdrawal, withdrawal_id)
    if not item:
        raise HTTPException(404, "WITHDRAWAL_NOT_FOUND")
    decision = _platform_decision(
        principal,
        request,
        action="WITHDRAWAL_EVIDENCE_READ",
        resource_type="WITHDRAWAL",
        resource_id=str(item.id),
    )

    wallet = db.get(Wallet, item.wallet_id)
    ledger = list(
        db.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.biz_type == "WITHDRAWAL",
                LedgerEntry.biz_id == str(item.id),
            )
            .order_by(LedgerEntry.created_at, LedgerEntry.id)
        )
    )

    payload = {
        "withdrawal": {
            "id": str(item.id),
            "userId": str(item.user_id),
            "amount": item.amount,
            "status": item.status,
            "provider": item.provider,
            "providerTxnId": item.provider_txn_id,
            "failureReason": item.failure_reason,
            "createdAt": item.created_at,
            "completedAt": item.completed_at,
            "rejectedAt": item.rejected_at,
        },
        "wallet": (
            {
                "id": str(wallet.id),
                "availableBalance": wallet.available_balance,
                "frozenBalance": wallet.frozen_balance,
                "version": wallet.version,
            }
            if wallet
            else None
        ),
        "ledger": [
            {
                "id": str(entry.id),
                "entryType": entry.entry_type,
                "amount": entry.amount,
                "balanceAfter": entry.balance_after,
                "createdAt": entry.created_at,
            }
            for entry in ledger
        ],
    }
    AuthorizationAudit.record(db, decision=decision)
    db.commit()
    return payload


@router.post("/withdrawals/{withdrawal_id}/complete")
def complete_withdrawal(
    withdrawal_id: uuid.UUID,
    body: WithdrawalComplete,
    request: Request,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        decision = _platform_decision(
            principal,
            request,
            action="WITHDRAWAL_COMPLETE",
            resource_type="WITHDRAWAL",
            resource_id=str(withdrawal_id),
        )
        item = WithdrawalService.complete(
            db,
            withdrawal_id=withdrawal_id,
            provider_txn_id=body.provider_txn_id.strip(),
            authorization=decision,
        )
        return {"id": str(item.id), "status": item.status_text, "statusCode": item.status}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/withdrawals/{withdrawal_id}/reject")
def reject_withdrawal(
    withdrawal_id: uuid.UUID,
    request: Request,
    reason: str = Query(default="REJECTED_BY_PLATFORM", max_length=256),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        decision = _platform_decision(
            principal,
            request,
            action="WITHDRAWAL_REJECT",
            resource_type="WITHDRAWAL",
            resource_id=str(withdrawal_id),
        )
        item = WithdrawalService.reject(
            db,
            withdrawal_id=withdrawal_id,
            reason=reason,
            authorization=decision,
        )
        return {"id": str(item.id), "status": item.status_text, "statusCode": item.status}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
