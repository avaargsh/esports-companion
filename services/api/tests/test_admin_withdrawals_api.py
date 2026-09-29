import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Wallet


def test_admin_withdrawal_completion_requires_real_payout_reference():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        identities = client.get("/api/v1/dev/demo-identities").json()
        player_user_id = demo["playerUserId"]
        admin_user_id = identities["admin"]["userId"]

        with SessionLocal() as db:
            wallet = db.scalar(
                select(Wallet).where(Wallet.user_id == uuid.UUID(player_user_id))
            )
            if wallet is None:
                wallet = Wallet(
                    user_id=uuid.UUID(player_user_id),
                    available_balance=10000,
                    frozen_balance=0,
                    version=0,
                )
                db.add(wallet)
            else:
                wallet.available_balance = 10000
                wallet.frozen_balance = 0
            db.commit()

        requested = client.post(
            "/api/v1/withdrawals",
            headers={
                "X-User-Id": player_user_id,
                "Idempotency-Key": f"admin-withdrawal-{uuid.uuid4()}",
            },
            json={"amount": 2500},
        )
        assert requested.status_code == 201
        withdrawal_id = requested.json()["id"]

        missing_reference = client.post(
            f"/api/v1/admin/withdrawals/{withdrawal_id}/complete",
            headers={"X-Admin-Id": admin_user_id},
        )
        assert missing_reference.status_code == 422

        blank_reference = client.post(
            f"/api/v1/admin/withdrawals/{withdrawal_id}/complete",
            headers={"X-Admin-Id": admin_user_id},
            json={"provider_txn_id": "   "},
        )
        assert blank_reference.status_code == 422

        completed = client.post(
            f"/api/v1/admin/withdrawals/{withdrawal_id}/complete",
            headers={"X-Admin-Id": admin_user_id},
            json={"provider_txn_id": "wechat-transfer-20260929-001"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"

        rows = client.get(
            "/api/v1/admin/withdrawals",
            headers={"X-Admin-Id": admin_user_id},
        )
        assert rows.status_code == 200
        item = next(row for row in rows.json() if row["id"] == withdrawal_id)
        assert item["providerTxnId"] == "wechat-transfer-20260929-001"
