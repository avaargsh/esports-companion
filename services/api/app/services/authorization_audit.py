from sqlalchemy.orm import Session

from app.models import OutboxEvent
from app.services.resource_authorization_policy import AuthorizationDecision


class AuthorizationAudit:
    @staticmethod
    def record(
        db: Session,
        *,
        decision: AuthorizationDecision,
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_type="AUDIT",
            aggregate_id=f"{decision.resource_type}:{decision.resource_id}",
            event_type="AUTHORIZATION_DECISION",
            payload_json=decision.as_payload(),
        )
        db.add(event)
        return event
