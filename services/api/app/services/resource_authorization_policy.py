import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorizationDecision:
    actor_user_id: uuid.UUID
    actor_roles: tuple[str, ...]
    action: str
    resource_type: str
    resource_id: str
    scope: str
    decision: str = "ALLOW"

    def as_payload(self) -> dict:
        return {
            "actorUserId": str(self.actor_user_id),
            "actorRoles": list(self.actor_roles),
            "action": self.action,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "scope": self.scope,
            "decision": self.decision,
        }


class ResourceAuthorizationPolicy:
    """Authorization contract for non-order resources.

    Route guards establish authentication/RBAC. This policy establishes the
    relationship between an actor and a concrete resource, and returns a
    structured allow decision that can be persisted as audit evidence.
    """

    @staticmethod
    def require_owner(
        *,
        actor_user_id: uuid.UUID,
        actor_roles: tuple[str, ...],
        owner_user_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: str,
        denial_code: str = "RESOURCE_NOT_OWNED",
    ) -> AuthorizationDecision:
        if actor_user_id != owner_user_id:
            raise PermissionError(denial_code)
        return AuthorizationDecision(
            actor_user_id=actor_user_id,
            actor_roles=actor_roles,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            scope="OWNER",
        )

    @staticmethod
    def require_platform(
        *,
        actor_user_id: uuid.UUID,
        actor_roles: tuple[str, ...],
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> AuthorizationDecision:
        if "PLATFORM" not in actor_roles:
            raise PermissionError("PLATFORM_REQUIRED")
        return AuthorizationDecision(
            actor_user_id=actor_user_id,
            actor_roles=actor_roles,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            scope="PLATFORM",
        )
