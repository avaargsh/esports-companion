from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Withdrawal
from app.schemas import WithdrawalCreate, WithdrawalOut
from app.security import Principal, require_player
from app.services.resource_authorization_policy import ResourceAuthorizationPolicy
from app.services.withdrawal_service import WithdrawalService

router = APIRouter(prefix="/api/v1/withdrawals", tags=["withdrawals"])


def _authorize_self(principal: Principal, *, action: str, resource_id: str) -> None:
    ResourceAuthorizationPolicy.require_owner(
        actor_user_id=principal.user_id,
        actor_roles=principal.roles,
        owner_user_id=principal.user_id,
        action=action,
        resource_type="WITHDRAWAL",
        resource_id=resource_id,
        denial_code="WITHDRAWAL_ACCESS_DENIED",
    )


@router.post("", response_model=WithdrawalOut, status_code=201)
def request_withdrawal(
    body: WithdrawalCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    _authorize_self(principal, action="WITHDRAWAL_REQUEST", resource_id="new")
    try:
        return WithdrawalService.request(
            db,
            user_id=principal.user_id,
            amount=body.amount,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("", response_model=list[WithdrawalOut])
def list_withdrawals(
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
    _authorize_self(principal, action="WITHDRAWAL_LIST", resource_id="collection")
    return list(
        db.scalars(
            select(Withdrawal)
            .where(Withdrawal.user_id == principal.user_id)
            .order_by(Withdrawal.created_at.desc())
            .limit(100)
        )
    )
