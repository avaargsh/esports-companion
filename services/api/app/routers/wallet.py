import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LedgerEntry, Wallet
from app.security import current_user_id

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


@router.get("")
def get_wallet(
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
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
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
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
