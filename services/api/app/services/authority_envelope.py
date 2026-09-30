import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.resource_authorization_policy import AuthorizationDecision


AUTHORITY_ENVELOPE_VERSION = "authority-envelope.v1"


def _issued_at() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuthorityEnvelope:
    """Execution authority bound to an exact resource snapshot and write intent."""

    authorization: AuthorizationDecision
    expected_state: dict[str, Any]
    bounded_write: dict[str, Any]
    resource_version: str
    approval_id: str | None = None
    envelope_version: str = AUTHORITY_ENVELOPE_VERSION
    issued_at: str = field(default_factory=_issued_at)

    def canonical_payload(self) -> dict:
        return {
            "envelopeVersion": self.envelope_version,
            "authorization": self.authorization.as_payload(),
            "expectedState": self.expected_state,
            "boundedWrite": self.bounded_write,
            "resourceVersion": self.resource_version,
            "approvalId": self.approval_id,
            "issuedAt": self.issued_at,
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def as_payload(self) -> dict:
        payload = self.canonical_payload()
        payload["digestAlgorithm"] = "sha256"
        payload["authorityDigest"] = self.digest
        return payload
