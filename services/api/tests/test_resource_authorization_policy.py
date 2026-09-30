import asyncio
import uuid

import pytest
from fastapi import Request
from sqlalchemy import select

from app.db import SessionLocal
from app.main import resource_authorization_denied
from app.models import OutboxEvent
from app.services.resource_authorization_policy import (
    POLICY_VERSION,
    ResourceAuthorizationDenied,
    ResourceAuthorizationPolicy,
)


def test_owner_decision_captures_v2_evidence_context():
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    decision = ResourceAuthorizationPolicy.require_owner(
        actor_user_id=user_id,
        actor_roles=("USER", "PLAYER"),
        owner_user_id=user_id,
        action="WITHDRAWAL_LIST",
        resource_type="WITHDRAWAL",
        resource_id="collection",
        session_id=session_id,
        request_id="request-owner-1",
        business_evidence_ref="WITHDRAWAL:collection",
    )

    payload = decision.as_payload()
    assert decision.scope == "OWNER"
    assert decision.decision == "ALLOW"
    assert decision.actor_user_id == user_id
    assert payload["actorRoles"] == ["USER", "PLAYER"]
    assert payload["reasonCode"] == "OWNER_MATCH"
    assert payload["policyVersion"] == POLICY_VERSION
    assert payload["sessionId"] == str(session_id)
    assert payload["requestId"] == "request-owner-1"
    assert payload["businessEvidenceRef"] == "WITHDRAWAL:collection"
    assert payload["occurredAt"].endswith("+00:00")


def test_owner_denial_carries_structured_evidence():
    actor_id = uuid.uuid4()

    with pytest.raises(ResourceAuthorizationDenied) as exc:
        ResourceAuthorizationPolicy.require_owner(
            actor_user_id=actor_id,
            actor_roles=("USER",),
            owner_user_id=uuid.uuid4(),
            action="WALLET_READ",
            resource_type="WALLET",
            resource_id="wallet-1",
            denial_code="WALLET_ACCESS_DENIED",
            request_id="request-deny-1",
        )

    decision = exc.value.decision
    assert str(exc.value) == "WALLET_ACCESS_DENIED"
    assert decision.decision == "DENY"
    assert decision.reason_code == "WALLET_ACCESS_DENIED"
    assert decision.policy_version == POLICY_VERSION
    assert decision.request_id == "request-deny-1"


def test_platform_decision_requires_platform_role():
    actor_id = uuid.uuid4()
    session_id = uuid.uuid4()

    decision = ResourceAuthorizationPolicy.require_platform(
        actor_user_id=actor_id,
        actor_roles=("USER", "PLATFORM"),
        action="PLAYER_APPROVE",
        resource_type="PLAYER_PROFILE",
        resource_id="player-1",
        session_id=session_id,
        request_id="request-platform-1",
    )
    assert decision.scope == "PLATFORM"
    assert decision.actor_user_id == actor_id
    assert decision.reason_code == "PLATFORM_ROLE"
    assert decision.session_id == session_id

    with pytest.raises(ResourceAuthorizationDenied, match="PLATFORM_REQUIRED") as exc:
        ResourceAuthorizationPolicy.require_platform(
            actor_user_id=actor_id,
            actor_roles=("USER",),
            action="PLAYER_APPROVE",
            resource_type="PLAYER_PROFILE",
            resource_id="player-1",
        )
    assert exc.value.decision.decision == "DENY"
    assert exc.value.decision.reason_code == "PLATFORM_REQUIRED"


def test_denied_decision_is_persisted_with_request_correlation():
    actor_id = uuid.uuid4()
    resource_id = f"wallet-{uuid.uuid4()}"

    with pytest.raises(ResourceAuthorizationDenied) as exc:
        ResourceAuthorizationPolicy.require_owner(
            actor_user_id=actor_id,
            actor_roles=("USER",),
            owner_user_id=uuid.uuid4(),
            action="WALLET_READ",
            resource_type="WALLET",
            resource_id=resource_id,
            denial_code="WALLET_ACCESS_DENIED",
        )

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test/denied",
            "headers": [],
        }
    )
    request.state.request_id = "request-deny-persisted"
    response = asyncio.run(resource_authorization_denied(request, exc.value))

    assert response.status_code == 403
    with SessionLocal() as db:
        audit = db.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_type == "AUDIT",
                OutboxEvent.aggregate_id == f"WALLET:{resource_id}",
                OutboxEvent.event_type == "AUTHORIZATION_DECISION",
            )
        )
        assert audit is not None
        assert audit.payload_json["decision"] == "DENY"
        assert audit.payload_json["reasonCode"] == "WALLET_ACCESS_DENIED"
        assert audit.payload_json["requestId"] == "request-deny-persisted"
        assert audit.payload_json["policyVersion"] == POLICY_VERSION
