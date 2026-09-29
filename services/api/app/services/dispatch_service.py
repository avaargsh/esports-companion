import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, OrderAssignment, PlayerProfile
from app.services.order_service import OrderService


class OrderAlreadyClaimed(RuntimeError):
    pass


class PlayerNotEligible(RuntimeError):
    pass


class AssignmentNotFound(LookupError):
    pass


class DispatchService:
    @staticmethod
    def claim(
        db: Session,
        *,
        order_id: uuid.UUID,
        player_id: uuid.UUID,
        expected_version: int,
    ) -> Order:
        player = db.get(PlayerProfile, player_id)
        if not player or player.verification_status != "APPROVED":
            raise PlayerNotEligible("PLAYER_NOT_ELIGIBLE")

        order = db.get(Order, order_id)
        if not order:
            raise LookupError("ORDER_NOT_FOUND")
        if order.user_id == player.user_id:
            raise PlayerNotEligible("CANNOT_CLAIM_OWN_ORDER")
        if order.status != OrderStatus.MATCHING.value:
            raise OrderAlreadyClaimed("ORDER_ALREADY_ACCEPTED")

        result = db.execute(
            update(Order)
            .where(
                Order.id == order_id,
                Order.status == OrderStatus.MATCHING.value,
                Order.version == expected_version,
            )
            .values(
                status=OrderStatus.ACCEPTED.value,
                version=Order.version + 1,
                accepted_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            db.rollback()
            raise OrderAlreadyClaimed("ORDER_ALREADY_ACCEPTED")

        db.add(
            OrderAssignment(
                order_id=order_id,
                player_id=player_id,
                status="ACTIVE",
                assigned_by="PLAYER",
                accepted_at=datetime.now(timezone.utc),
            )
        )
        db.flush()
        db.refresh(order)
        OrderService._record(
            db,
            order,
            "PLAYER_CLAIMED",
            OrderStatus.MATCHING.value,
            OrderStatus.ACCEPTED.value,
            "PLAYER",
            str(player_id),
            {},
        )
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def active_assignment(db: Session, order_id: uuid.UUID) -> OrderAssignment:
        assignment = db.scalar(
            select(OrderAssignment).where(
                OrderAssignment.order_id == order_id,
                OrderAssignment.status == "ACTIVE",
            )
        )
        if not assignment:
            raise AssignmentNotFound("ACTIVE_ASSIGNMENT_NOT_FOUND")
        return assignment

    @staticmethod
    def start(db: Session, *, order: Order, player_id: uuid.UUID) -> Order:
        assignment = DispatchService.active_assignment(db, order.id)
        if assignment.player_id != player_id:
            raise PermissionError("NOT_ORDER_PLAYER")
        OrderService.transition(
            db,
            order,
            OrderStatus.IN_SERVICE,
            event_type="SERVICE_STARTED",
            actor_type="PLAYER",
            actor_id=str(player_id),
        )
        db.commit()
        return order

    @staticmethod
    def finish(db: Session, *, order: Order, player_id: uuid.UUID) -> Order:
        assignment = DispatchService.active_assignment(db, order.id)
        if assignment.player_id != player_id:
            raise PermissionError("NOT_ORDER_PLAYER")
        OrderService.transition(
            db,
            order,
            OrderStatus.FINISH_REQUESTED,
            event_type="FINISH_REQUESTED",
            actor_type="PLAYER",
            actor_id=str(player_id),
        )
        db.commit()
        return order
