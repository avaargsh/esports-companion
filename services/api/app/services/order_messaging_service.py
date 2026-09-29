import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Order,
    OrderAssignment,
    OrderMessage,
    OutboxEvent,
    PlayerProfile,
)


class OrderMessagingService:
    SENDABLE_STATUSES = {
        "ACCEPTED",
        "IN_SERVICE",
        "FINISH_REQUESTED",
        "DISPUTED",
    }

    @staticmethod
    def _player_profile(db: Session, user_id: uuid.UUID) -> PlayerProfile | None:
        return db.scalar(
            select(PlayerProfile).where(PlayerProfile.user_id == user_id)
        )

    @staticmethod
    def participant_role(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
        require_active_assignment: bool = False,
    ) -> str:
        if "PLATFORM" in roles and not require_active_assignment:
            return "PLATFORM"
        if order.user_id == user_id:
            if require_active_assignment:
                active = db.scalar(
                    select(OrderAssignment.id).where(
                        OrderAssignment.order_id == order.id,
                        OrderAssignment.status == "ACTIVE",
                    )
                )
                if not active:
                    raise PermissionError("ORDER_CHAT_NOT_ACTIVE")
            return "USER"

        if "PLAYER" in roles:
            player = OrderMessagingService._player_profile(db, user_id)
            if player:
                stmt = select(OrderAssignment.id).where(
                    OrderAssignment.order_id == order.id,
                    OrderAssignment.player_id == player.id,
                )
                if require_active_assignment:
                    stmt = stmt.where(OrderAssignment.status == "ACTIVE")
                assignment = db.scalar(stmt.order_by(OrderAssignment.created_at.desc()))
                if assignment:
                    return "PLAYER"

        raise PermissionError("ORDER_MESSAGE_ACCESS_DENIED")

    @staticmethod
    def list_messages(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
        limit: int = 100,
    ) -> list[OrderMessage]:
        OrderMessagingService.participant_role(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
        )
        rows = list(
            db.scalars(
                select(OrderMessage)
                .where(OrderMessage.order_id == order.id)
                .order_by(OrderMessage.created_at.desc(), OrderMessage.id.desc())
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
        if order.status not in OrderMessagingService.SENDABLE_STATUSES:
            raise ValueError("ORDER_CHAT_NOT_SENDABLE")

        sender_role = OrderMessagingService.participant_role(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
            require_active_assignment=True,
        )
        if sender_role == "PLATFORM":
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
            sender_role=sender_role,
            message_type="TEXT",
            content=normalized_content,
            client_message_id=client_message_id,
        )
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
                    "senderRole": sender_role,
                },
            )
        )
        db.commit()
        db.refresh(message)
        return message
