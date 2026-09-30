import asyncio
import uuid

import pytest
from fastapi import Request
from sqlalchemy import select

from app.db import SessionLocal
from app.main import authority_admission_denied
from app.models import OutboxEvent
from app.services.authority_admission import (
    AUTHORITY_ADMISSION_VERSION,
    AuthorityAdmission,
    AuthorityAdmissionDenied,
)
from app.services.authority_envelope import AuthorityEnvelope
from app.services.resource_authorization_policy import AuthorizationDecision


def _authority() -> AuthorityEnvelope:
    decision = AuthorizationDecision(
        actor_user_id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
        actor_roles=("USER", "PLATFORM"),
        action="WITHDRAWAL_COMPLETE",
        resource_type="WITHDRAWAL",
        resource_id="00000000-0000-0000-0000-000000000201",
        scope="PLATFORM",
        decision="ALLOW",
        reason_code="PLATFORM_ROLE",
        session_id=uuid.UUID("00000000-0000-0000-0000-000000000301"),
        request_id="admission-request-1",
        business_evidence_ref=(
            "WITHDRAWAL:00000000-0000-0000-0000-000000000201"
        ),
        occurred_at="2026-09-30T00:00:00+00:00",
    )
    return AuthorityEnvelope(
        authorization=decision,
        expected_state={
            "withdrawalStatus": "PENDING",
            "withdrawalAmount": 2500,
            "walletId": "00000000-0000-0000-0000-000000000401",
            "walletVersion": 7,
            "walletAvailableBalance": 7500,
            "walletFrozenBalance": 2500,
        },
        bounded_write={
            "operation": "WITHDRAWAL_COMPLETE",
            "providerTxnId": "payout-1",
            "withdrawalStatus": "COMPLETED",
            "walletFrozenDelta": -2500,
        },
        resource_version=(
            "withdrawal:00000000-0000-0000-0000-000000000201:status=PENDING;"
            "wallet:00000000-0000-0000-0000-000000000401:v7"
        ),
        issued_at="2026-09-30T00:00:01+00:00",
    )


def test_authority_admission_exact_match_admits():
    authority = _authority()

    admission = AuthorityAdmission.admit(
        authority=authority,
        current_state=dict(authority.expected_state),
        current_resource_version=authority.resource_version,
        requested_write=dict(authority.bounded_write),
    )

    assert admission.decision == "ADMIT"
    assert admission.reason_code == "AUTHORITY_EXACT_MATCH"
    assert admission.admission_version == AUTHORITY_ADMISSION_VERSION
    assert admission.authority_digest == authority.digest
    assert admission.state_diff == {}
    assert admission.write_diff == {}


def test_authority_admission_denies_state_drift():
    authority = _authority()
    current_state = dict(authority.expected_state)
    current_state["walletVersion"] = 8
    current_version = authority.resource_version.replace(":v7", ":v8")

    with pytest.raises(AuthorityAdmissionDenied) as exc:
        AuthorityAdmission.admit(
            authority=authority,
            current_state=current_state,
            current_resource_version=current_version,
            requested_write=dict(authority.bounded_write),
        )

    admission = exc.value.admission
    assert admission.decision == "DENY"
    assert admission.reason_code == "AUTHORITY_STATE_DRIFT"
    assert admission.state_diff == {
        "walletVersion": {"expected": 7, "current": 8}
    }
    assert admission.current_resource_version == current_version


def test_authority_admission_denies_bounded_write_mismatch():
    authority = _authority()
    requested_write = dict(authority.bounded_write)
    requested_write["providerTxnId"] = "payout-2"

    with pytest.raises(AuthorityAdmissionDenied) as exc:
        AuthorityAdmission.admit(
            authority=authority,
            current_state=dict(authority.expected_state),
            current_resource_version=authority.resource_version,
            requested_write=requested_write,
        )

    admission = exc.value.admission
    assert admission.decision == "DENY"
    assert admission.reason_code == "AUTHORITY_BOUNDED_WRITE_MISMATCH"
    assert admission.write_diff == {
        "providerTxnId": {
            "expected": "payout-1",
            "current": "payout-2",
        }
    }


def test_denied_authority_admission_is_persisted():
    authority = _authority()
    current_state = dict(authority.expected_state)
    current_state["walletVersion"] = 9

    with pytest.raises(AuthorityAdmissionDenied) as exc:
        AuthorityAdmission.admit(
            authority=authority,
            current_state=current_state,
            current_resource_version=authority.resource_version.replace(":v7", ":v9"),
            requested_write=dict(authority.bounded_write),
        )

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/test/authority-admission",
            "headers": [],
        }
    )
    response = asyncio.run(authority_admission_denied(request, exc.value))

    assert response.status_code == 409
    with SessionLocal() as db:
        event = db.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.aggregate_type == "AUDIT",
                OutboxEvent.aggregate_id
                == (
                    "WITHDRAWAL:"
                    "00000000-0000-0000-0000-000000000201"
                ),
                OutboxEvent.event_type == "AUTHORITY_ADMISSION",
            )
            .order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc())
        )
        assert event is not None
        payload = event.payload_json
        assert payload["admission"]["decision"] == "DENY"
        assert payload["admission"]["reasonCode"] == "AUTHORITY_STATE_DRIFT"
        assert payload["admission"]["authorityDigest"] == authority.digest
        assert payload["authorityEnvelope"]["authorityDigest"] == authority.digest
