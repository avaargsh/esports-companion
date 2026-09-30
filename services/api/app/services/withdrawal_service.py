import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Wallet, Withdrawal
from app.services.authorization_audit import AuthorizationAudit
from app.services.authority_admission import AuthorityAdmission
from app.services.authority_envelope import AuthorityEnvelope
from app.services.resource_authorization_policy import AuthorizationDecision


class WithdrawalService:
    @staticmethod
    def _resource_version(
        *,
        withdrawal_id: uuid.UUID,
        withdrawal_status: str,
        wallet_id: uuid.UUID,
        wallet_version: int | None,
    ) -> str:
        wallet_version_value = (
            f"v{wallet_version}" if wallet_version is not None else "missing"
        )
        return (
            f"withdrawal:{withdrawal_id}:status={withdrawal_status};"
            f"wallet:{wallet_id}:{wallet_version_value}"
        )

    @staticmethod
    def _read_authority_snapshot(
        db: Session,
        *,
        withdrawal_id: uuid.UUID,
    ) -> tuple[dict[str, Any], str] | None:
        withdrawal_row = db.execute(
            select(
                Withdrawal.id.label("withdrawal_id"),
                Withdrawal.status.label("withdrawal_status"),
                Withdrawal.amount.label("withdrawal_amount"),
                Withdrawal.wallet_id.label("wallet_id"),
            ).where(Withdrawal.id == withdrawal_id)
        ).mappings().one_or_none()
        if not withdrawal_row:
            return None

        wallet_row = db.execute(
            select(
                Wallet.id.label("wallet_id"),
                Wallet.version.label("wallet_version"),
                Wallet.available_balance.label("wallet_available_balance"),
                Wallet.frozen_balance.label("wallet_frozen_balance"),
            ).where(Wallet.id == withdrawal_row["wallet_id"])
        ).mappings().one_or_none()

        state = {
            "withdrawalStatus": withdrawal_row["withdrawal_status"],
            "withdrawalAmount": withdrawal_row["withdrawal_amount"],
            "walletId": str(withdrawal_row["wallet_id"]),
            "walletVersion": (
                wallet_row["wallet_version"] if wallet_row is not None else None
            ),
            "walletAvailableBalance": (
                wallet_row["wallet_available_balance"]
                if wallet_row is not None
                else None
            ),
            "walletFrozenBalance": (
                wallet_row["wallet_frozen_balance"] if wallet_row is not None else None
            ),
        }
        resource_version = WithdrawalService._resource_version(
            withdrawal_id=withdrawal_row["withdrawal_id"],
            withdrawal_status=withdrawal_row["withdrawal_status"],
            wallet_id=withdrawal_row["wallet_id"],
            wallet_version=(
                wallet_row["wallet_version"] if wallet_row is not None else None
            ),
        )
        return state, resource_version

    @staticmethod
    def _locked_authority_snapshot(
        *,
        withdrawal: Withdrawal,
        wallet: Wallet,
    ) -> tuple[dict[str, Any], str]:
        state = {
            "withdrawalStatus": withdrawal.status,
            "withdrawalAmount": withdrawal.amount,
            "walletId": str(wallet.id),
            "walletVersion": wallet.version,
            "walletAvailableBalance": wallet.available_balance,
            "walletFrozenBalance": wallet.frozen_balance,
        }
        resource_version = WithdrawalService._resource_version(
            withdrawal_id=withdrawal.id,
            withdrawal_status=withdrawal.status,
            wallet_id=wallet.id,
            wallet_version=wallet.version,
        )
        return state, resource_version

    @staticmethod
    def request(
        db: Session,
        *,
        user_id: uuid.UUID,
        amount: int,
        idempotency_key: str,
        authorization: AuthorizationDecision | None = None,
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
            if authorization is not None:
                AuthorizationAudit.record(
                    db,
                    decision=replace(
                        authorization,
                        resource_id=str(existing.id),
                        business_evidence_ref=f"WITHDRAWAL:{existing.id}",
                    ),
                )
                db.commit()
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
        if authorization is not None:
            AuthorizationAudit.record(
                db,
                decision=replace(
                    authorization,
                    resource_id=str(withdrawal.id),
                    business_evidence_ref=f"WITHDRAWAL:{withdrawal.id}",
                ),
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
        preliminary = WithdrawalService._read_authority_snapshot(
            db,
            withdrawal_id=withdrawal_id,
        )
        if preliminary is None:
            raise LookupError("WITHDRAWAL_NOT_FOUND")

        preliminary_state, preliminary_resource_version = preliminary
        authority = None
        if (
            authorization is not None
            and preliminary_state["withdrawalStatus"] == "PENDING"
        ):
            if not provider_txn_id or not provider_txn_id.strip():
                raise ValueError("WITHDRAWAL_PAYOUT_REFERENCE_REQUIRED")
            normalized_provider_txn_id = provider_txn_id.strip()
            authority = AuthorityEnvelope(
                authorization=authorization,
                expected_state=preliminary_state,
                bounded_write={
                    "operation": "WITHDRAWAL_COMPLETE",
                    "providerTxnId": normalized_provider_txn_id,
                    "withdrawalStatus": "COMPLETED",
                    "walletFrozenDelta": -preliminary_state["withdrawalAmount"],
                },
                resource_version=preliminary_resource_version,
            )

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
        if not wallet:
            raise ValueError("WITHDRAWAL_FROZEN_BALANCE_INVALID")

        current_state, current_resource_version = (
            WithdrawalService._locked_authority_snapshot(
                withdrawal=withdrawal,
                wallet=wallet,
            )
        )
        admission = None
        if authorization is not None and authority is not None:
            requested_write = {
                "operation": "WITHDRAWAL_COMPLETE",
                "providerTxnId": provider_txn_id,
                "withdrawalStatus": "COMPLETED",
                "walletFrozenDelta": -withdrawal.amount,
            }
            admission = AuthorityAdmission.admit(
                authority=authority,
                current_state=current_state,
                current_resource_version=current_resource_version,
                requested_write=requested_write,
            )
        elif authorization is not None and withdrawal.status == "PENDING":
            raise ValueError("AUTHORITY_ENVELOPE_NOT_ISSUED")

        if withdrawal.status != "PENDING":
            raise ValueError("WITHDRAWAL_NOT_PENDING")
        if wallet.frozen_balance < withdrawal.amount:
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
            AuthorizationAudit.record_admission(
                db,
                authority=authority,
                admission=admission,
            )
            AuthorizationAudit.record(
                db,
                decision=authorization,
                authority=authority,
            )
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
        preliminary = WithdrawalService._read_authority_snapshot(
            db,
            withdrawal_id=withdrawal_id,
        )
        if preliminary is None:
            raise LookupError("WITHDRAWAL_NOT_FOUND")

        preliminary_state, preliminary_resource_version = preliminary
        normalized_reason = reason[:256]
        authority = None
        if (
            authorization is not None
            and preliminary_state["withdrawalStatus"] == "PENDING"
        ):
            authority = AuthorityEnvelope(
                authorization=authorization,
                expected_state=preliminary_state,
                bounded_write={
                    "operation": "WITHDRAWAL_REJECT",
                    "reason": normalized_reason,
                    "withdrawalStatus": "REJECTED",
                    "walletFrozenDelta": -preliminary_state["withdrawalAmount"],
                    "walletAvailableDelta": preliminary_state["withdrawalAmount"],
                },
                resource_version=preliminary_resource_version,
            )

        withdrawal = db.scalar(
            select(Withdrawal)
            .where(Withdrawal.id == withdrawal_id)
            .with_for_update()
        )
        if not withdrawal:
            raise LookupError("WITHDRAWAL_NOT_FOUND")
        if withdrawal.status == "REJECTED":
            return withdrawal

        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == withdrawal.wallet_id)
            .with_for_update()
        )
        if not wallet:
            raise ValueError("WITHDRAWAL_FROZEN_BALANCE_INVALID")

        current_state, current_resource_version = (
            WithdrawalService._locked_authority_snapshot(
                withdrawal=withdrawal,
                wallet=wallet,
            )
        )
        admission = None
        if authorization is not None and authority is not None:
            requested_write = {
                "operation": "WITHDRAWAL_REJECT",
                "reason": normalized_reason,
                "withdrawalStatus": "REJECTED",
                "walletFrozenDelta": -withdrawal.amount,
                "walletAvailableDelta": withdrawal.amount,
            }
            admission = AuthorityAdmission.admit(
                authority=authority,
                current_state=current_state,
                current_resource_version=current_resource_version,
                requested_write=requested_write,
            )
        elif authorization is not None and withdrawal.status == "PENDING":
            raise ValueError("AUTHORITY_ENVELOPE_NOT_ISSUED")

        if withdrawal.status != "PENDING":
            raise ValueError("WITHDRAWAL_NOT_PENDING")
        if wallet.frozen_balance < withdrawal.amount:
            raise ValueError("WITHDRAWAL_FROZEN_BALANCE_INVALID")

        wallet.frozen_balance -= withdrawal.amount
        wallet.available_balance += withdrawal.amount
        wallet.version += 1
        withdrawal.status = "REJECTED"
        withdrawal.failure_reason = normalized_reason
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
            AuthorizationAudit.record_admission(
                db,
                authority=authority,
                admission=admission,
            )
            AuthorizationAudit.record(
                db,
                decision=authorization,
                authority=authority,
            )
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
