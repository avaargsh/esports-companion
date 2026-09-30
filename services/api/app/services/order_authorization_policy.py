import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderAssignment, PlayerProfile


@dataclass(frozen=True)
class OrderActor:
    role: str
    assignment: OrderAssignment | None = None


class OrderAuthorizationPolicy:
    """Single authorization contract for order-scoped resources.

    The policy intentionally separates:
    - ownership: the customer who created the order;
    - participation: the currently active assigned player;
    - historical participation: a former assigned player reading only their
      own participation window;
    - platform oversight: platform staff with broad read access.

    Domain services may layer state-machine rules on top of these identity and
    relationship checks, but should not reimplement relationship discovery.
    """

    @staticmethod
    def require_owner(
        order: Order,
        *,
        user_id: uuid.UUID,
    ) -> OrderActor:
        if order.user_id != user_id:
            raise PermissionError("ORDER_NOT_OWNED")
        return OrderActor(role="USER")

    @staticmethod
    def require_viewer(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
    ) -> OrderActor:
        if order.user_id == user_id:
            return OrderActor(role="USER")
        if "PLATFORM" in roles:
            return OrderActor(role="PLATFORM")

        assignment = OrderAuthorizationPolicy._player_assignment(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
            active_only=True,
        )
        if assignment:
            return OrderActor(role="PLAYER", assignment=assignment)
        raise PermissionError("ORDER_ACCESS_DENIED")

    @staticmethod
    def require_dispute_actor(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
    ) -> OrderActor:
        if order.user_id == user_id:
            return OrderActor(role="USER")

        assignment = OrderAuthorizationPolicy._player_assignment(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
            active_only=True,
        )
        if assignment:
            return OrderActor(role="PLAYER", assignment=assignment)
        raise PermissionError("DISPUTE_ACTOR_NOT_ORDER_PARTICIPANT")

    @staticmethod
    def require_chat_reader(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
    ) -> OrderActor:
        if order.user_id == user_id:
            return OrderActor(role="USER")
        if "PLATFORM" in roles:
            return OrderActor(role="PLATFORM")

        assignment = OrderAuthorizationPolicy._player_assignment(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
            active_only=False,
        )
        if assignment:
            return OrderActor(role="PLAYER", assignment=assignment)
        raise PermissionError("ORDER_MESSAGE_ACCESS_DENIED")

    @staticmethod
    def require_chat_sender(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
    ) -> OrderActor:
        if "PLATFORM" in roles:
            return OrderActor(role="PLATFORM")

        if order.user_id == user_id:
            active = db.scalar(
                select(OrderAssignment.id).where(
                    OrderAssignment.order_id == order.id,
                    OrderAssignment.status == "ACTIVE",
                )
            )
            if not active:
                raise PermissionError("ORDER_CHAT_NOT_ACTIVE")
            return OrderActor(role="USER")

        assignment = OrderAuthorizationPolicy._player_assignment(
            db,
            order=order,
            user_id=user_id,
            roles=roles,
            active_only=True,
        )
        if assignment:
            return OrderActor(role="PLAYER", assignment=assignment)
        raise PermissionError("ORDER_MESSAGE_ACCESS_DENIED")

    @staticmethod
    def _player_assignment(
        db: Session,
        *,
        order: Order,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
        active_only: bool,
    ) -> OrderAssignment | None:
        if "PLAYER" not in roles:
            return None

        player = db.scalar(
            select(PlayerProfile).where(PlayerProfile.user_id == user_id)
        )
        if not player:
            return None

        stmt = select(OrderAssignment).where(
            OrderAssignment.order_id == order.id,
            OrderAssignment.player_id == player.id,
        )
        if active_only:
            stmt = stmt.where(OrderAssignment.status == "ACTIVE")
        return db.scalar(stmt.order_by(OrderAssignment.created_at.desc()))
