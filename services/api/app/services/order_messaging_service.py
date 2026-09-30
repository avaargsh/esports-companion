import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Order, OrderMessage, OutboxEvent
from app.services.order_authorization_policy import OrderAuthorizationPolicy


class OrderMessagingService:
    SENDABLE_STATUSES = {
        "ACCEPTED",
        "IN_SERVICE",
        "FINISH_REQUESTED",
        "DISPUTED",
    }

    @staticmethod
    def list_messages(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
        limit: int = 100,
    ) -> list[OrderMessage]:
        actor = OrderAuthorizationPolicy.require_chat_reader(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
        )
        stmt = select(OrderMessage).where(OrderMessage.order_id == order.id)

        if actor.role == "PLAYER":
            assignment = actor.assignment
            if not assignment:
                raise PermissionError("ORDER_MESSAGE_ACCESS_DENIED")

            participation_started_at = assignment.accepted_at or assignment.created_at
            stmt = stmt.where(OrderMessage.created_at >= participation_started_at)
            if assignment.status != "ACTIVE":
                if not assignment.released_at:
                    raise PermissionError("ORDER_MESSAGE_ACCESS_DENIED")
                stmt = stmt.where(OrderMessage.created_at <= assignment.released_at)

        rows = list(
            db.scalars(
                stmt.order_by(OrderMessage.created_at.desc(), OrderMessage.id.desc())
                .limit(limit)
            )
        )
        rows.reverse()
        return rows

    @staticmethod
    def create_message(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
        client_message_id: str,
        content: str,
    ) -> OrderMessage:
        # Authorize before exposing state-machine details. Historical participants
        # may inspect their own chat window, but unrelated users must not learn
        # whether an order is currently sendable.
        OrderAuthorizationPolicy.require_chat_reader(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
        )
        if order.status not in OrderMessagingService.SENDABLE_STATUSES:
            raise ValueError("ORDER_CHAT_NOT_SENDABLE")

        actor = OrderAuthorizationPolicy.require_chat_sender(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
        )
        if actor.role == "PLATFORM":
            raise PermissionError("PLATFORM_CHAT_SEND_DISABLED")

        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("MESSAGE_CONTENT_REQUIRED")

        existing = db.scalar(
            select(OrderMessage).where(
                OrderMessage.order_id == order.id,
                OrderMessage.sender_user_id == user_id,
                OrderMessage.client_message_id == client_message_id,
            )
        )
        if existing:
            if existing.content != normalized_content:
                raise ValueError("CLIENT_MESSAGE_ID_REUSED")
            return existing

        message = OrderMessage(
            order_id=order.id,
            sender_user_id=user_id,
            sender_role=actor.role,
            message_type="TEXT",
            content=normalized_content,
            client_message_id=client_message_id,
        )
        try:
            db.add(message)
            db.flush()
            db.add(
                OutboxEvent(
                    aggregate_type="ORDER",
                    aggregate_id=str(order.id),
                    event_type="ORDER_MESSAGE_CREATED",
                    payload_json={
                        "orderId": str(order.id),
                        "messageId": str(message.id),
                        "senderUserId": str(user_id),
                        "senderRole": actor.role,
                    },
                )
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(OrderMessage).where(
                    OrderMessage.order_id == order.id,
                    OrderMessage.sender_user_id == user_id,
                    OrderMessage.client_message_id == client_message_id,
                )
            )
            if existing:
                if existing.content != normalized_content:
                    raise ValueError("CLIENT_MESSAGE_ID_REUSED")
                return existing
            raise
        db.refresh(message)
        return message
