import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import LedgerEntry, Wallet, Withdrawal
from app.tools.withdrawal_acceptance import build_withdrawal_acceptance


def test_completed_real_withdrawal_acceptance_passes():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        user_id = uuid.uuid4()
        wallet = Wallet(
            user_id=user_id,
            available_balance=800,
            frozen_balance=0,
            version=2,
        )
        db.add(wallet)
        db.flush()

        withdrawal = Withdrawal(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=200,
            status="COMPLETED",
            provider="MANUAL",
            provider_txn_id="real-payout-001",
            idempotency_key="withdrawal-acceptance-001",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(withdrawal)
        db.flush()
        db.add_all(
            [
                LedgerEntry(
                    account_id=wallet.id,
                    biz_type="WITHDRAWAL",
                    biz_id=str(withdrawal.id),
                    entry_type="WITHDRAWAL_FROZEN",
                    amount=-200,
                    balance_after=800,
                ),
                LedgerEntry(
                    account_id=wallet.id,
                    biz_type="WITHDRAWAL",
                    biz_id=str(withdrawal.id),
                    entry_type="WITHDRAWAL_COMPLETED",
                    amount=0,
                    balance_after=800,
                ),
            ]
        )
        db.commit()

        report = build_withdrawal_acceptance(
            db,
            withdrawal_id=withdrawal.id,
            expected_payout_ref="real-payout-001",
        )

        assert report["status"] == "PASS"
        assert all(report["checks"].values())


def test_real_withdrawal_acceptance_detects_wrong_payout_reference():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        user_id = uuid.uuid4()
        wallet = Wallet(
            user_id=user_id,
            available_balance=800,
            frozen_balance=0,
            version=2,
        )
        db.add(wallet)
        db.flush()

        withdrawal = Withdrawal(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=200,
            status="COMPLETED",
            provider="MANUAL",
            provider_txn_id="real-payout-001",
            idempotency_key="withdrawal-acceptance-002",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(withdrawal)
        db.flush()
        db.add_all(
            [
                LedgerEntry(
                    account_id=wallet.id,
                    biz_type="WITHDRAWAL",
                    biz_id=str(withdrawal.id),
                    entry_type="WITHDRAWAL_FROZEN",
                    amount=-200,
                    balance_after=800,
                ),
                LedgerEntry(
                    account_id=wallet.id,
                    biz_type="WITHDRAWAL",
                    biz_id=str(withdrawal.id),
                    entry_type="WITHDRAWAL_COMPLETED",
                    amount=0,
                    balance_after=800,
                ),
            ]
        )
        db.commit()

        report = build_withdrawal_acceptance(
            db,
            withdrawal_id=withdrawal.id,
            expected_payout_ref="different-payout",
        )

        assert report["status"] == "FAIL"
        assert report["checks"]["expectedPayoutReference"] is False
