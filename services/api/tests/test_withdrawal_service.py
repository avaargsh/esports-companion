import uuid

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import LedgerEntry, PlayerProfile, User, Wallet, Withdrawal
from app.services.withdrawal_service import WithdrawalService


def _create_player_wallet(balance: int):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        user = User(
            nickname=f"withdraw-player-{suffix}",
            role="USER",
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
        db.add(
            PlayerProfile(
                user_id=user.id,
                display_name=f"Withdraw Player {suffix}",
                verification_status="APPROVED",
                service_status="AVAILABLE",
            )
        )
        wallet = Wallet(
            user_id=user.id,
            available_balance=balance,
            frozen_balance=0,
            version=0,
        )
        db.add(wallet)
        db.commit()
        return user.id, wallet.id


def test_withdrawal_request_is_idempotent_and_freezes_balance():
    user_id, wallet_id = _create_player_wallet(10000)

    with SessionLocal() as db:
        first = WithdrawalService.request(
            db,
            user_id=user_id,
            amount=3000,
            idempotency_key=f"wd:{uuid.uuid4()}",
        )
        key = first.idempotency_key
        second = WithdrawalService.request(
            db,
            user_id=user_id,
            amount=3000,
            idempotency_key=key,
        )

        assert first.id == second.id
        wallet = db.get(Wallet, wallet_id)
        assert wallet.available_balance == 7000
        assert wallet.frozen_balance == 3000
        assert db.scalar(
            select(func.count())
            .select_from(Withdrawal)
            .where(Withdrawal.user_id == user_id)
        ) == 1
        assert db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(
                LedgerEntry.biz_type == "WITHDRAWAL",
                LedgerEntry.biz_id == str(first.id),
            )
        ) == 1


def test_withdrawal_complete_is_idempotent():
    user_id, wallet_id = _create_player_wallet(10000)

    with SessionLocal() as db:
        item = WithdrawalService.request(
            db,
            user_id=user_id,
            amount=2500,
            idempotency_key=f"wd:{uuid.uuid4()}",
        )
        first = WithdrawalService.complete(
            db,
            withdrawal_id=item.id,
            provider_txn_id="manual:test",
        )
        second = WithdrawalService.complete(
            db,
            withdrawal_id=item.id,
            provider_txn_id="manual:test",
        )

        assert first.id == second.id
        assert first.status == "COMPLETED"
        wallet = db.get(Wallet, wallet_id)
        assert wallet.available_balance == 7500
        assert wallet.frozen_balance == 0


def test_withdrawal_reject_releases_frozen_balance():
    user_id, wallet_id = _create_player_wallet(10000)

    with SessionLocal() as db:
        item = WithdrawalService.request(
            db,
            user_id=user_id,
            amount=4000,
            idempotency_key=f"wd:{uuid.uuid4()}",
        )
        rejected = WithdrawalService.reject(
            db,
            withdrawal_id=item.id,
            reason="TEST_REJECT",
        )

        assert rejected.status == "REJECTED"
        wallet = db.get(Wallet, wallet_id)
        assert wallet.available_balance == 10000
        assert wallet.frozen_balance == 0


def test_withdrawal_rejects_insufficient_balance():
    user_id, wallet_id = _create_player_wallet(1000)

    with SessionLocal() as db:
        with pytest.raises(ValueError, match="INSUFFICIENT_AVAILABLE_BALANCE"):
            WithdrawalService.request(
                db,
                user_id=user_id,
                amount=2000,
                idempotency_key=f"wd:{uuid.uuid4()}",
            )
        wallet = db.get(Wallet, wallet_id)
        assert wallet.available_balance == 1000
        assert wallet.frozen_balance == 0
