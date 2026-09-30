import argparse
import json
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import LedgerEntry, Wallet, Withdrawal


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def build_withdrawal_acceptance(
    db: Session,
    *,
    withdrawal_id: uuid.UUID,
    expected_payout_ref: str | None = None,
) -> dict:
    withdrawal = db.get(Withdrawal, withdrawal_id)
    if not withdrawal:
        return {
            "status": "FAIL",
            "checks": {"withdrawalExists": False},
            "facts": {"withdrawalId": str(withdrawal_id)},
        }

    wallet = db.get(Wallet, withdrawal.wallet_id)
    ledger = list(
        db.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.biz_type == "WITHDRAWAL",
                LedgerEntry.biz_id == str(withdrawal.id),
            )
            .order_by(LedgerEntry.created_at, LedgerEntry.id)
        )
    )

    payout_ref = (withdrawal.provider_txn_id or "").strip()
    payout_ref_count = 0
    if payout_ref:
        payout_ref_count = int(
            db.scalar(
                select(func.count(Withdrawal.id)).where(
                    Withdrawal.provider == withdrawal.provider,
                    Withdrawal.provider_txn_id == payout_ref,
                )
            )
            or 0
        )

    frozen_entries = [
        item for item in ledger if item.entry_type == "WITHDRAWAL_FROZEN"
    ]
    completed_entries = [
        item for item in ledger if item.entry_type == "WITHDRAWAL_COMPLETED"
    ]
    frozen = frozen_entries[0] if len(frozen_entries) == 1 else None
    completed = completed_entries[0] if len(completed_entries) == 1 else None

    checks = {
        "withdrawalExists": True,
        "statusCompleted": withdrawal.status == "COMPLETED",
        "manualPayoutProvider": withdrawal.provider == "MANUAL",
        "payoutReferencePresent": bool(payout_ref),
        "expectedPayoutReference": (
            True
            if expected_payout_ref is None
            else payout_ref == expected_payout_ref.strip()
        ),
        "payoutReferenceUnique": bool(payout_ref) and payout_ref_count == 1,
        "completionTimestampPresent": withdrawal.completed_at is not None,
        "rejectionTimestampAbsent": withdrawal.rejected_at is None,
        "walletLinked": wallet is not None,
        "walletBalancesNonNegative": (
            wallet is not None
            and wallet.available_balance >= 0
            and wallet.frozen_balance >= 0
        ),
        "singleFrozenLedgerEntry": len(frozen_entries) == 1,
        "singleCompletedLedgerEntry": len(completed_entries) == 1,
        "frozenAmountMatches": (
            frozen is not None and frozen.amount == -withdrawal.amount
        ),
        "completionDoesNotDoubleDebit": (
            frozen is not None
            and completed is not None
            and completed.amount == 0
            and completed.balance_after == frozen.balance_after
        ),
    }

    facts = {
        "withdrawal": {
            "id": str(withdrawal.id),
            "userId": str(withdrawal.user_id),
            "walletId": str(withdrawal.wallet_id),
            "amount": withdrawal.amount,
            "status": withdrawal.status,
            "provider": withdrawal.provider,
            "providerTxnId": withdrawal.provider_txn_id,
            "createdAt": iso(withdrawal.created_at),
            "completedAt": iso(withdrawal.completed_at),
            "rejectedAt": iso(withdrawal.rejected_at),
        },
        "wallet": (
            {
                "availableBalance": wallet.available_balance,
                "frozenBalance": wallet.frozen_balance,
                "version": wallet.version,
            }
            if wallet
            else None
        ),
        "ledger": [
            {
                "entryType": item.entry_type,
                "amount": item.amount,
                "balanceAfter": item.balance_after,
                "createdAt": iso(item.created_at),
            }
            for item in ledger
        ],
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "facts": facts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify one completed real-withdrawal acceptance record."
    )
    parser.add_argument("--withdrawal-id", required=True)
    parser.add_argument("--expected-payout-ref")
    args = parser.parse_args()

    try:
        withdrawal_id = uuid.UUID(args.withdrawal_id)
    except ValueError as exc:
        raise SystemExit("WITHDRAWAL_ID_INVALID") from exc

    with SessionLocal() as db:
        report = build_withdrawal_acceptance(
            db,
            withdrawal_id=withdrawal_id,
            expected_payout_ref=args.expected_payout_ref,
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
