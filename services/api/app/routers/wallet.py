from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LedgerEntry, Wallet
from app.security import Principal, current_principal
from app.services.resource_authorization_policy import ResourceAuthorizationPolicy

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


def _authorize_wallet(principal: Principal, action: str) -> None:
    ResourceAuthorizationPolicy.require_owner(
        actor_user_id=principal.user_id,
        actor_roles=principal.roles,
        owner_user_id=principal.user_id,
        action=action,
        resource_type="WALLET",
        resource_id=str(principal.user_id),
        denial_code="WALLET_ACCESS_DENIED",
    )


@router.get("")
def get_wallet(
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    _authorize_wallet(principal, "WALLET_READ")
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == principal.user_id))
    if not wallet:
        return {"availableBalance": 0, "frozenBalance": 0}
    return {
        "id": str(wallet.id),
        "availableBalance": wallet.available_balance,
        "frozenBalance": wallet.frozen_balance,
        "version": wallet.version,
    }


@router.get("/ledger")
def ledger(
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    _authorize_wallet(principal, "WALLET_LEDGER_READ")
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == principal.user_id))
    if not wallet:
        return []
    entries = db.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.account_id == wallet.id)
        .order_by(LedgerEntry.created_at.desc())
    ).all()
    return [
        {
            "id": str(entry.id),
            "bizType": entry.biz_type,
            "bizId": entry.biz_id,
            "entryType": entry.entry_type,
            "amount": entry.amount,
            "balanceAfter": entry.balance_after,
            "createdAt": entry.created_at,
        }
        for entry in entries
    ]
