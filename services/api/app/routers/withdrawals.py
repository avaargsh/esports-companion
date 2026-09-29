from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Withdrawal
from app.schemas import WithdrawalCreate, WithdrawalOut
from app.security import Principal, require_player
from app.services.withdrawal_service import WithdrawalService

router = APIRouter(prefix="/api/v1/withdrawals", tags=["withdrawals"])


@router.post("", response_model=WithdrawalOut, status_code=201)
def request_withdrawal(
    body: WithdrawalCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_player),
    db: Session = Depends(get_db),
):
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
    return list(
        db.scalars(
            select(Withdrawal)
            .where(Withdrawal.user_id == principal.user_id)
            .order_by(Withdrawal.created_at.desc())
            .limit(100)
        )
    )
