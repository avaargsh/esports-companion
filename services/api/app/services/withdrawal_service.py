import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Wallet, Withdrawal
from app.services.authorization_audit import AuthorizationAudit
from app.services.resource_authorization_policy import AuthorizationDecision


class WithdrawalService:
    @staticmethod
    def request(
        db: Session,
        *,
        user_id: uuid.UUID,
        amount: int,
        idempotency_key: str,
    ) -> Withdrawal:
        if amount <= 0:
            raise ValueError("WITHDRAWAL_AMOUNT_INVALID")

        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        if not wallet:
            raise ValueError("WALLET_NOT_FOUND")

        existing = db.scalar(
            select(Withdrawal).where(
                Withdrawal.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.user_id != user_id or existing.amount != amount:
                raise ValueError("IDEMPOTENCY_KEY_REUSED")
            return existing

        if wallet.available_balance < amount:
            raise ValueError("INSUFFICIENT_AVAILABLE_BALANCE")

        withdrawal = Withdrawal(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            status="PENDING",
            provider="MANUAL",
            idempotency_key=idempotency_key,
        )
        db.add(withdrawal)
        db.flush()

        wallet.available_balance -= amount
        wallet.frozen_balance += amount
        wallet.version += 1
        db.add(
            LedgerEntry(
                account_id=wallet.id,
                biz_type="WITHDRAWAL",
                biz_id=str(withdrawal.id),
                entry_type="WITHDRAWAL_FROZEN",
                amount=-amount,
                balance_after=wallet.available_balance,
            )
        )
        db.commit()
        db.refresh(withdrawal)
        return withdrawal

    @staticmethod
    def complete(
        db: Session,
        *,
        withdrawal_id: uuid.UUID,
        provider_txn_id: str | None = None,
        authorization: AuthorizationDecision | None = None,
    ) -> Withdrawal:
        withdrawal = db.scalar(
            select(Withdrawal)
            .where(Withdrawal.id == withdrawal_id)
            .with_for_update()
        )
        if not withdrawal:
            raise LookupError("WITHDRAWAL_NOT_FOUND")
        if withdrawal.status == "COMPLETED":
            if (
                provider_txn_id
                and withdrawal.provider_txn_id
                and withdrawal.provider_txn_id != provider_txn_id
            ):
                raise ValueError("WITHDRAWAL_PAYOUT_REFERENCE_MISMATCH")
            return withdrawal
        if withdrawal.status != "PENDING":
            raise ValueError("WITHDRAWAL_NOT_PENDING")

        if not provider_txn_id or not provider_txn_id.strip():
            raise ValueError("WITHDRAWAL_PAYOUT_REFERENCE_REQUIRED")
        provider_txn_id = provider_txn_id.strip()

        reused = db.scalar(
            select(Withdrawal.id).where(
                Withdrawal.provider == withdrawal.provider,
                Withdrawal.provider_txn_id == provider_txn_id,
                Withdrawal.id != withdrawal.id,
            )
        )
        if reused:
            raise ValueError("WITHDRAWAL_PAYOUT_REFERENCE_REUSED")

        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == withdrawal.wallet_id)
            .with_for_update()
        )
        if not wallet or wallet.frozen_balance < withdrawal.amount:
            raise ValueError("WITHDRAWAL_FROZEN_BALANCE_INVALID")

        wallet.frozen_balance -= withdrawal.amount
        wallet.version += 1
        withdrawal.status = "COMPLETED"
        withdrawal.provider_txn_id = provider_txn_id
        withdrawal.completed_at = datetime.now(timezone.utc)

        db.add(
            LedgerEntry(
                account_id=wallet.id,
                biz_type="WITHDRAWAL",
                biz_id=str(withdrawal.id),
                entry_type="WITHDRAWAL_COMPLETED",
                amount=0,
                balance_after=wallet.available_balance,
            )
        )
        if authorization is not None:
            AuthorizationAudit.record(db, decision=authorization)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            reused = db.scalar(
                select(Withdrawal.id).where(
                    Withdrawal.provider == withdrawal.provider,
                    Withdrawal.provider_txn_id == provider_txn_id,
                    Withdrawal.id != withdrawal.id,
                )
            )
            if reused:
                raise ValueError("WITHDRAWAL_PAYOUT_REFERENCE_REUSED")
            raise
        db.refresh(withdrawal)
        return withdrawal

    @staticmethod
    def reject(
        db: Session,
        *,
        withdrawal_id: uuid.UUID,
        reason: str,
        authorization: AuthorizationDecision | None = None,
    ) -> Withdrawal:
        withdrawal = db.scalar(
            select(Withdrawal)
            .where(Withdrawal.id == withdrawal_id)
            .with_for_update()
        )
        if not withdrawal:
            raise LookupError("WITHDRAWAL_NOT_FOUND")
        if withdrawal.status == "REJECTED":
            return withdrawal
        if withdrawal.status != "PENDING":
            raise ValueError("WITHDRAWAL_NOT_PENDING")

        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == withdrawal.wallet_id)
            .with_for_update()
        )
        if not wallet or wallet.frozen_balance < withdrawal.amount:
            raise ValueError("WITHDRAWAL_FROZEN_BALANCE_INVALID")

        wallet.frozen_balance -= withdrawal.amount
        wallet.available_balance += withdrawal.amount
        wallet.version += 1
        withdrawal.status = "REJECTED"
        withdrawal.failure_reason = reason[:256]
        withdrawal.rejected_at = datetime.now(timezone.utc)

        db.add(
            LedgerEntry(
                account_id=wallet.id,
                biz_type="WITHDRAWAL",
                biz_id=str(withdrawal.id),
                entry_type="WITHDRAWAL_RELEASED",
                amount=withdrawal.amount,
                balance_after=wallet.available_balance,
            )
        )
        if authorization is not None:
            AuthorizationAudit.record(db, decision=authorization)
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
