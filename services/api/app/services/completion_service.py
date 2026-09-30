import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import Order
from app.services.order_authorization_policy import OrderAuthorizationPolicy
from app.services.order_service import OrderNotFound, OrderService
from app.services.settlement_service import SettlementService


class CompletionService:
    @staticmethod
    def confirm_by_user(
        db: Session,
        *,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Order:
        order = db.scalar(
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
        )
        if not order:
            raise OrderNotFound(str(order_id))
        OrderAuthorizationPolicy.require_owner(order, user_id=user_id)
        if order.status == OrderStatus.SETTLED.value:
            return order
        CompletionService.complete_and_settle(
            db,
            order=order,
            event_type="USER_CONFIRMED_FINISH",
            actor_type="USER",
            actor_id=str(user_id),
            payload={},
        )
        return order

    @staticmethod
    def complete_and_settle(
        db: Session,
        *,
        order: Order,
        event_type: str,
        actor_type: str,
        actor_id: str | None,
        payload: dict,
    ) -> None:
        if order.status != OrderStatus.FINISH_REQUESTED.value:
            raise ValueError("ORDER_NOT_AWAITING_CONFIRMATION")

        OrderService.transition(
            db,
            order,
            OrderStatus.COMPLETED,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )
        SettlementService.settle(db, order)
