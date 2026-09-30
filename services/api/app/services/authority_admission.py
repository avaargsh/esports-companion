from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.authority_envelope import AuthorityEnvelope


AUTHORITY_ADMISSION_VERSION = "authority-admission.v1"


def _admitted_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _diff(expected: dict[str, Any], current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = sorted(set(expected) | set(current))
    return {
        key: {
            "expected": expected.get(key),
            "current": current.get(key),
        }
        for key in keys
        if expected.get(key) != current.get(key)
    }


@dataclass(frozen=True)
class AuthorityAdmissionDecision:
    authority_digest: str
    decision: str
    reason_code: str
    current_state: dict[str, Any]
    current_resource_version: str
    requested_write: dict[str, Any]
    state_diff: dict[str, dict[str, Any]]
    write_diff: dict[str, dict[str, Any]]
    admission_version: str = AUTHORITY_ADMISSION_VERSION
    admitted_at: str = field(default_factory=_admitted_at)

    def as_payload(self) -> dict:
        return {
            "admissionVersion": self.admission_version,
            "authorityDigest": self.authority_digest,
            "decision": self.decision,
            "reasonCode": self.reason_code,
            "currentState": self.current_state,
            "currentResourceVersion": self.current_resource_version,
            "requestedWrite": self.requested_write,
            "stateDiff": self.state_diff,
            "writeDiff": self.write_diff,
            "admittedAt": self.admitted_at,
        }


class AuthorityAdmissionDenied(PermissionError):
    def __init__(
        self,
        *,
        authority: AuthorityEnvelope,
        admission: AuthorityAdmissionDecision,
    ):
        super().__init__(admission.reason_code)
        self.authority = authority
        self.admission = admission


class AuthorityAdmission:
    @staticmethod
    def admit(
        *,
        authority: AuthorityEnvelope,
        current_state: dict[str, Any],
        current_resource_version: str,
        requested_write: dict[str, Any],
    ) -> AuthorityAdmissionDecision:
        state_diff = _diff(authority.expected_state, current_state)
        write_diff = _diff(authority.bounded_write, requested_write)

        if write_diff:
            admission = AuthorityAdmissionDecision(
                authority_digest=authority.digest,
                decision="DENY",
                reason_code="AUTHORITY_BOUNDED_WRITE_MISMATCH",
                current_state=current_state,
                current_resource_version=current_resource_version,
                requested_write=requested_write,
                state_diff=state_diff,
                write_diff=write_diff,
            )
            raise AuthorityAdmissionDenied(
                authority=authority,
                admission=admission,
            )

        if state_diff or authority.resource_version != current_resource_version:
            admission = AuthorityAdmissionDecision(
                authority_digest=authority.digest,
                decision="DENY",
                reason_code="AUTHORITY_STATE_DRIFT",
                current_state=current_state,
                current_resource_version=current_resource_version,
                requested_write=requested_write,
                state_diff=state_diff,
                write_diff=write_diff,
            )
            raise AuthorityAdmissionDenied(
                authority=authority,
                admission=admission,
            )

        return AuthorityAdmissionDecision(
            authority_digest=authority.digest,
            decision="ADMIT",
            reason_code="AUTHORITY_EXACT_MATCH",
            current_state=current_state,
            current_resource_version=current_resource_version,
            requested_write=requested_write,
            state_diff={},
            write_diff={},
        )
