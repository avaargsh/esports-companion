import uuid

import pytest

from app.services.resource_authorization_policy import ResourceAuthorizationPolicy


def test_owner_decision_captures_actor_resource_and_scope():
    user_id = uuid.uuid4()

    decision = ResourceAuthorizationPolicy.require_owner(
        actor_user_id=user_id,
        actor_roles=("USER", "PLAYER"),
        owner_user_id=user_id,
        action="WITHDRAWAL_LIST",
        resource_type="WITHDRAWAL",
        resource_id="collection",
    )

    assert decision.scope == "OWNER"
    assert decision.decision == "ALLOW"
    assert decision.actor_user_id == user_id
    assert decision.as_payload()["actorRoles"] == ["USER", "PLAYER"]


def test_owner_decision_denies_cross_user_resource():
    with pytest.raises(PermissionError, match="WALLET_ACCESS_DENIED"):
        ResourceAuthorizationPolicy.require_owner(
            actor_user_id=uuid.uuid4(),
            actor_roles=("USER",),
            owner_user_id=uuid.uuid4(),
            action="WALLET_READ",
            resource_type="WALLET",
            resource_id="wallet-1",
            denial_code="WALLET_ACCESS_DENIED",
        )


def test_platform_decision_requires_platform_role():
    actor_id = uuid.uuid4()

    decision = ResourceAuthorizationPolicy.require_platform(
        actor_user_id=actor_id,
        actor_roles=("USER", "PLATFORM"),
        action="PLAYER_APPROVE",
        resource_type="PLAYER_PROFILE",
        resource_id="player-1",
    )
    assert decision.scope == "PLATFORM"
    assert decision.actor_user_id == actor_id

    with pytest.raises(PermissionError, match="PLATFORM_REQUIRED"):
        ResourceAuthorizationPolicy.require_platform(
            actor_user_id=actor_id,
            actor_roles=("USER",),
            action="PLAYER_APPROVE",
            resource_type="PLAYER_PROFILE",
            resource_id="player-1",
        )
