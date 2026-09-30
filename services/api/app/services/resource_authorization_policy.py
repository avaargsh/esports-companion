import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


POLICY_VERSION = "resource-authz.v2"


def _occurred_at() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuthorizationDecision:
    actor_user_id: uuid.UUID
    actor_roles: tuple[str, ...]
    action: str
    resource_type: str
    resource_id: str
    scope: str
    decision: str
    reason_code: str
    policy_version: str = POLICY_VERSION
    session_id: uuid.UUID | None = None
    request_id: str | None = None
    business_evidence_ref: str | None = None
    occurred_at: str = field(default_factory=_occurred_at)

    def as_payload(self) -> dict:
        return {
            "actorUserId": str(self.actor_user_id),
            "actorRoles": list(self.actor_roles),
            "action": self.action,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "scope": self.scope,
            "decision": self.decision,
            "reasonCode": self.reason_code,
            "policyVersion": self.policy_version,
            "sessionId": str(self.session_id) if self.session_id else None,
            "requestId": self.request_id,
            "businessEvidenceRef": self.business_evidence_ref,
            "occurredAt": self.occurred_at,
        }


class ResourceAuthorizationDenied(PermissionError):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.reason_code)
        self.decision = decision


class ResourceAuthorizationPolicy:
    """Authorization contract for non-order resources.

    Route guards establish authentication/RBAC. This policy establishes the
    relationship between an actor and a concrete resource and returns a
    structured decision suitable for durable authorization evidence.
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
        session_id: uuid.UUID | None = None,
        request_id: str | None = None,
        business_evidence_ref: str | None = None,
    ) -> AuthorizationDecision:
        common = {
            "actor_user_id": actor_user_id,
            "actor_roles": actor_roles,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "scope": "OWNER",
            "session_id": session_id,
            "request_id": request_id,
            "business_evidence_ref": business_evidence_ref,
        }
        if actor_user_id != owner_user_id:
            raise ResourceAuthorizationDenied(
                AuthorizationDecision(
                    **common,
                    decision="DENY",
                    reason_code=denial_code,
                )
            )
        return AuthorizationDecision(
            **common,
            decision="ALLOW",
            reason_code="OWNER_MATCH",
        )

    @staticmethod
    def require_platform(
        *,
        actor_user_id: uuid.UUID,
        actor_roles: tuple[str, ...],
        action: str,
        resource_type: str,
        resource_id: str,
        session_id: uuid.UUID | None = None,
        request_id: str | None = None,
        business_evidence_ref: str | None = None,
    ) -> AuthorizationDecision:
        common = {
            "actor_user_id": actor_user_id,
            "actor_roles": actor_roles,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "scope": "PLATFORM",
            "session_id": session_id,
            "request_id": request_id,
            "business_evidence_ref": business_evidence_ref,
        }
        if "PLATFORM" not in actor_roles:
            raise ResourceAuthorizationDenied(
                AuthorizationDecision(
                    **common,
                    decision="DENY",
                    reason_code="PLATFORM_REQUIRED",
                )
            )
        return AuthorizationDecision(
            **common,
            decision="ALLOW",
            reason_code="PLATFORM_ROLE",
        )
