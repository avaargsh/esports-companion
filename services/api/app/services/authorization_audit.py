from sqlalchemy.orm import Session

from app.models import OutboxEvent
from app.services.authority_admission import AuthorityAdmissionDecision
from app.services.authority_envelope import AuthorityEnvelope
from app.services.resource_authorization_policy import AuthorizationDecision


class AuthorizationAudit:
    @staticmethod
    def record(
        db: Session,
        *,
        decision: AuthorizationDecision,
        authority: AuthorityEnvelope | None = None,
    ) -> OutboxEvent:
        payload = decision.as_payload()
        if authority is not None:
            payload["authorityEnvelope"] = authority.as_payload()

        event = OutboxEvent(
            aggregate_type="AUDIT",
            aggregate_id=f"{decision.resource_type}:{decision.resource_id}",
            event_type="AUTHORIZATION_DECISION",
            payload_json=payload,
        )
        db.add(event)
        return event


    @staticmethod
    def record_admission(
        db: Session,
        *,
        authority: AuthorityEnvelope,
        admission: AuthorityAdmissionDecision,
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_type="AUDIT",
            aggregate_id=(
                f"{authority.authorization.resource_type}:"
                f"{authority.authorization.resource_id}"
            ),
            event_type="AUTHORITY_ADMISSION",
            payload_json={
                "authorization": authority.authorization.as_payload(),
                "authorityEnvelope": authority.as_payload(),
                "admission": admission.as_payload(),
            },
        )
        db.add(event)
        return event
