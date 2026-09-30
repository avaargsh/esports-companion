import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import OutboxEvent, Wallet


def test_admin_withdrawal_completion_requires_real_payout_reference():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        platform_login = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-platform"},
        )
        assert platform_login.status_code == 200
        admin_user_id = platform_login.json()["userId"]
        access_token = platform_login.json()["accessToken"]
        sessions = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert sessions.status_code == 200
        session_id = next(
            item["sessionId"] for item in sessions.json() if item["current"]
        )

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

        withdrawal_request_id = f"withdrawal-request-{uuid.uuid4().hex}"
        requested = client.post(
            "/api/v1/withdrawals",
            headers={
                "X-User-Id": player_user_id,
                "X-Request-Id": withdrawal_request_id,
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

        complete_request_id = f"withdrawal-complete-{uuid.uuid4().hex}"
        completed = client.post(
            f"/api/v1/admin/withdrawals/{withdrawal_id}/complete",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Request-Id": complete_request_id,
            },
            json={"provider_txn_id": "wechat-transfer-20260929-001"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"

        rows = client.get(
            "/api/v1/admin/withdrawals",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert rows.status_code == 200
        item = next(row for row in rows.json() if row["id"] == withdrawal_id)
        assert item["providerTxnId"] == "wechat-transfer-20260929-001"

        evidence_request_id = f"withdrawal-evidence-{uuid.uuid4().hex}"
        evidence = client.get(
            f"/api/v1/admin/withdrawals/{withdrawal_id}/evidence",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Request-Id": evidence_request_id,
            },
        )
        assert evidence.status_code == 200
        payload = evidence.json()
        assert payload["withdrawal"]["providerTxnId"] == "wechat-transfer-20260929-001"
        assert payload["wallet"]["availableBalance"] == 7500
        assert payload["wallet"]["frozenBalance"] == 0
        assert [entry["entryType"] for entry in payload["ledger"]] == [
            "WITHDRAWAL_FROZEN",
            "WITHDRAWAL_COMPLETED",
        ]

        with SessionLocal() as db:
            audits = list(
                db.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.aggregate_type == "AUDIT",
                        OutboxEvent.aggregate_id == f"WITHDRAWAL:{withdrawal_id}",
                        OutboxEvent.event_type == "AUTHORIZATION_DECISION",
                    )
                    .order_by(OutboxEvent.created_at, OutboxEvent.id)
                )
            )
            payloads = [item.payload_json for item in audits]
            request_audit = next(
                item for item in payloads if item["action"] == "WITHDRAWAL_REQUEST"
            )
            assert request_audit["actorUserId"] == player_user_id
            assert request_audit["scope"] == "OWNER"
            assert request_audit["decision"] == "ALLOW"
            assert request_audit["reasonCode"] == "OWNER_MATCH"
            assert request_audit["policyVersion"] == "resource-authz.v2"
            assert request_audit["sessionId"] is None
            assert request_audit["requestId"] == withdrawal_request_id
            assert (
                request_audit["businessEvidenceRef"]
                == f"WITHDRAWAL:{withdrawal_id}"
            )

            complete_audit = next(
                item for item in payloads if item["action"] == "WITHDRAWAL_COMPLETE"
            )
            assert complete_audit["actorUserId"] == admin_user_id
            assert complete_audit["scope"] == "PLATFORM"
            assert complete_audit["decision"] == "ALLOW"
            assert complete_audit["reasonCode"] == "PLATFORM_ROLE"
            assert complete_audit["policyVersion"] == "resource-authz.v2"
            assert complete_audit["sessionId"] == session_id
            assert complete_audit["requestId"] == complete_request_id
            assert (
                complete_audit["businessEvidenceRef"]
                == f"WITHDRAWAL:{withdrawal_id}"
            )
            authority = complete_audit["authorityEnvelope"]
            assert authority["envelopeVersion"] == "authority-envelope.v1"
            assert authority["digestAlgorithm"] == "sha256"
            assert len(authority["authorityDigest"]) == 64
            assert authority["approvalId"] is None
            assert authority["authorization"]["requestId"] == complete_request_id
            assert authority["authorization"]["sessionId"] == session_id
            assert authority["expectedState"]["withdrawalStatus"] == "PENDING"
            assert authority["expectedState"]["withdrawalAmount"] == 2500
            assert authority["expectedState"]["walletAvailableBalance"] == 7500
            assert authority["expectedState"]["walletFrozenBalance"] == 2500
            assert authority["boundedWrite"] == {
                "operation": "WITHDRAWAL_COMPLETE",
                "providerTxnId": "wechat-transfer-20260929-001",
                "withdrawalStatus": "COMPLETED",
                "walletFrozenDelta": -2500,
            }
            assert (
                authority["resourceVersion"]
                == (
                    f"withdrawal:{withdrawal_id}:status=PENDING;"
                    f"wallet:{authority['expectedState']['walletId']}:"
                    f"v{authority['expectedState']['walletVersion']}"
                )
            )

            admission_event = db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "AUDIT",
                    OutboxEvent.aggregate_id == f"WITHDRAWAL:{withdrawal_id}",
                    OutboxEvent.event_type == "AUTHORITY_ADMISSION",
                )
            )
            assert admission_event is not None
            admission_payload = admission_event.payload_json
            admission = admission_payload["admission"]
            assert admission["decision"] == "ADMIT"
            assert admission["reasonCode"] == "AUTHORITY_EXACT_MATCH"
            assert admission["admissionVersion"] == "authority-admission.v1"
            assert admission["authorityDigest"] == authority["authorityDigest"]
            assert admission["currentState"] == authority["expectedState"]
            assert admission["currentResourceVersion"] == authority["resourceVersion"]
            assert admission["requestedWrite"] == authority["boundedWrite"]
            assert admission["stateDiff"] == {}
            assert admission["writeDiff"] == {}

            read_audit = next(
                item
                for item in payloads
                if item["action"] == "WITHDRAWAL_EVIDENCE_READ"
            )
            assert read_audit["decision"] == "ALLOW"
            assert read_audit["sessionId"] == session_id
            assert read_audit["requestId"] == evidence_request_id
            assert read_audit["policyVersion"] == "resource-authz.v2"


def test_admin_withdrawal_reject_binds_request_and_session_evidence():
    with TestClient(app) as client:
        demo = client.get("/api/v1/dev/bootstrap").json()
        player_user_id = demo["playerUserId"]
        platform_login = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-platform"},
        )
        assert platform_login.status_code == 200
        admin_user_id = platform_login.json()["userId"]
        access_token = platform_login.json()["accessToken"]
        sessions = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        session_id = next(
            item["sessionId"] for item in sessions.json() if item["current"]
        )

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
                "Idempotency-Key": f"reject-withdrawal-{uuid.uuid4()}",
            },
            json={"amount": 1200},
        )
        assert requested.status_code == 201
        withdrawal_id = requested.json()["id"]

        reject_request_id = f"withdrawal-reject-{uuid.uuid4().hex}"
        rejected = client.post(
            f"/api/v1/admin/withdrawals/{withdrawal_id}/reject",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Request-Id": reject_request_id,
            },
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"

        with SessionLocal() as db:
            audit = db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "AUDIT",
                    OutboxEvent.aggregate_id == f"WITHDRAWAL:{withdrawal_id}",
                    OutboxEvent.event_type == "AUTHORIZATION_DECISION",
                    OutboxEvent.payload_json["action"].as_string()
                    == "WITHDRAWAL_REJECT",
                )
            )
            assert audit is not None
            assert audit.payload_json["actorUserId"] == admin_user_id
            assert audit.payload_json["sessionId"] == session_id
            assert audit.payload_json["requestId"] == reject_request_id
            assert audit.payload_json["businessEvidenceRef"] == (
                f"WITHDRAWAL:{withdrawal_id}"
            )
            authority = audit.payload_json["authorityEnvelope"]
            assert authority["envelopeVersion"] == "authority-envelope.v1"
            assert len(authority["authorityDigest"]) == 64
            assert authority["authorization"]["requestId"] == reject_request_id
            assert authority["authorization"]["sessionId"] == session_id
            assert authority["expectedState"]["withdrawalStatus"] == "PENDING"
            assert authority["expectedState"]["withdrawalAmount"] == 1200
            assert authority["expectedState"]["walletAvailableBalance"] == 8800
            assert authority["expectedState"]["walletFrozenBalance"] == 1200
            assert authority["boundedWrite"] == {
                "operation": "WITHDRAWAL_REJECT",
                "reason": "REJECTED_BY_PLATFORM",
                "withdrawalStatus": "REJECTED",
                "walletFrozenDelta": -1200,
                "walletAvailableDelta": 1200,
            }
            assert (
                authority["resourceVersion"]
                == (
                    f"withdrawal:{withdrawal_id}:status=PENDING;"
                    f"wallet:{authority['expectedState']['walletId']}:"
                    f"v{authority['expectedState']['walletVersion']}"
                )
            )

            admission_event = db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "AUDIT",
                    OutboxEvent.aggregate_id == f"WITHDRAWAL:{withdrawal_id}",
                    OutboxEvent.event_type == "AUTHORITY_ADMISSION",
                )
            )
            assert admission_event is not None
            admission = admission_event.payload_json["admission"]
            assert admission["decision"] == "ADMIT"
            assert admission["reasonCode"] == "AUTHORITY_EXACT_MATCH"
            assert admission["admissionVersion"] == "authority-admission.v1"
            assert admission["authorityDigest"] == authority["authorityDigest"]
            assert admission["currentState"] == authority["expectedState"]
            assert admission["currentResourceVersion"] == authority["resourceVersion"]
            assert admission["requestedWrite"] == authority["boundedWrite"]
            assert admission["stateDiff"] == {}
            assert admission["writeDiff"] == {}


def test_admin_withdrawal_evidence_returns_404_for_unknown_id():
    with TestClient(app) as client:
        client.get("/api/v1/dev/bootstrap")
        identities = client.get("/api/v1/dev/demo-identities").json()
        admin_user_id = identities["admin"]["userId"]

        response = client.get(
            "/api/v1/admin/withdrawals/00000000-0000-0000-0000-000000000001/evidence",
            headers={"X-Admin-Id": admin_user_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "WITHDRAWAL_NOT_FOUND"
