import uuid
from dataclasses import replace

from app.services.authority_envelope import (
    AUTHORITY_ENVELOPE_VERSION,
    AuthorityEnvelope,
)
from app.services.resource_authorization_policy import AuthorizationDecision


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        actor_user_id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
        actor_roles=("USER", "PLATFORM"),
        action="WITHDRAWAL_COMPLETE",
        resource_type="WITHDRAWAL",
        resource_id="00000000-0000-0000-0000-000000000201",
        scope="PLATFORM",
        decision="ALLOW",
        reason_code="PLATFORM_ROLE",
        session_id=uuid.UUID("00000000-0000-0000-0000-000000000301"),
        request_id="request-1",
        business_evidence_ref="WITHDRAWAL:00000000-0000-0000-0000-000000000201",
        occurred_at="2026-09-30T00:00:00+00:00",
    )


def test_authority_envelope_digest_is_canonical_and_stable():
    authority = AuthorityEnvelope(
        authorization=_decision(),
        expected_state={
            "withdrawalStatus": "PENDING",
            "walletVersion": 7,
            "walletFrozenBalance": 2500,
        },
        bounded_write={
            "operation": "WITHDRAWAL_COMPLETE",
            "providerTxnId": "payout-1",
            "withdrawalStatus": "COMPLETED",
        },
        resource_version=(
            "withdrawal:00000000-0000-0000-0000-000000000201:status=PENDING;"
            "wallet:00000000-0000-0000-0000-000000000401:v7"
        ),
        issued_at="2026-09-30T00:00:01+00:00",
    )

    first = authority.as_payload()
    second = authority.as_payload()

    assert first["envelopeVersion"] == AUTHORITY_ENVELOPE_VERSION
    assert first["digestAlgorithm"] == "sha256"
    assert first["authorityDigest"] == second["authorityDigest"]
    assert len(first["authorityDigest"]) == 64
    assert first["approvalId"] is None
    assert first["authorization"]["requestId"] == "request-1"


def test_authority_digest_changes_when_bounded_write_changes():
    authority = AuthorityEnvelope(
        authorization=_decision(),
        expected_state={
            "withdrawalStatus": "PENDING",
            "walletVersion": 7,
        },
        bounded_write={
            "operation": "WITHDRAWAL_COMPLETE",
            "providerTxnId": "payout-1",
        },
        resource_version="withdrawal:201:status=PENDING;wallet:401:v7",
        issued_at="2026-09-30T00:00:01+00:00",
    )
    changed = replace(
        authority,
        bounded_write={
            "operation": "WITHDRAWAL_COMPLETE",
            "providerTxnId": "payout-2",
        },
    )

    assert authority.digest != changed.digest


def test_authority_digest_changes_when_expected_state_changes():
    authority = AuthorityEnvelope(
        authorization=_decision(),
        expected_state={
            "withdrawalStatus": "PENDING",
            "walletVersion": 7,
        },
        bounded_write={"operation": "WITHDRAWAL_REJECT", "reason": "risk"},
        resource_version="withdrawal:201:status=PENDING;wallet:401:v7",
        issued_at="2026-09-30T00:00:01+00:00",
    )
    changed = replace(
        authority,
        expected_state={
            "withdrawalStatus": "PENDING",
            "walletVersion": 8,
        },
        resource_version="withdrawal:201:status=PENDING;wallet:401:v8",
    )

    assert authority.digest != changed.digest
