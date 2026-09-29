import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order, OrderAssignment, PlayerProfile, ProviderOffering
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
        if (
            not player
            or player.verification_status != "APPROVED"
            or player.service_status != "AVAILABLE"
        ):
            raise PlayerNotEligible("PLAYER_NOT_ELIGIBLE")

        order = db.get(Order, order_id)
        if not order:
            raise LookupError("ORDER_NOT_FOUND")
        if order.user_id == player.user_id:
            raise PlayerNotEligible("CANNOT_CLAIM_OWN_ORDER")
        if order.status != OrderStatus.MATCHING.value:
            raise OrderAlreadyClaimed("ORDER_ALREADY_ACCEPTED")

        offering = db.scalar(
            select(ProviderOffering).where(
                ProviderOffering.player_id == player.id,
                ProviderOffering.sku_id == order.sku_id,
                ProviderOffering.status == "ACTIVE",
            )
        )
        if not offering:
            raise PlayerNotEligible("PLAYER_NOT_OFFERING_SKU")

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
    def assign_designated(db: Session, *, order: Order) -> Order:
        if not order.designated_player_id:
            return order
        if order.status != OrderStatus.MATCHING.value:
            raise OrderAlreadyClaimed("ORDER_NOT_MATCHING")

        existing = db.scalar(
            select(OrderAssignment).where(
                OrderAssignment.order_id == order.id,
                OrderAssignment.status == "ACTIVE",
            )
        )
        if existing:
            return order

        player = db.get(PlayerProfile, order.designated_player_id)
        if not player:
            raise PlayerNotEligible("DESIGNATED_PLAYER_NOT_FOUND")

        db.add(
            OrderAssignment(
                order_id=order.id,
                player_id=player.id,
                status="ACTIVE",
                assigned_by="USER",
                accepted_at=datetime.now(timezone.utc),
            )
        )
        OrderService.transition(
            db,
            order,
            OrderStatus.ACCEPTED,
            event_type="DESIGNATED_PLAYER_ASSIGNED",
            actor_type="USER",
            actor_id=str(order.user_id),
            payload={"playerId": str(player.id)},
        )
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
