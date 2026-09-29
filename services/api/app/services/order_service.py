import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus, ensure_transition
from app.metrics import observe_order_transition
from app.models import (
    Game,
    Order,
    OrderEvent,
    OutboxEvent,
    PlayerProfile,
    ProviderOffering,
    ServiceSKU,
)


class OrderNotFound(LookupError):
    pass


class OrderService:
    @staticmethod
    def create_order(
        db: Session,
        *,
        user_id: uuid.UUID,
        sku_id: uuid.UUID | None = None,
        offering_id: uuid.UUID | None = None,
        quantity: int = 1,
        remark: str = "",
    ) -> Order:
        if bool(sku_id) == bool(offering_id):
            raise ValueError("ORDER_REQUIRES_EXACTLY_ONE_SKU_OR_OFFERING")

        designated_player_id = None
        if offering_id:
            offering = db.get(ProviderOffering, offering_id)
            if not offering or offering.status != "ACTIVE":
                raise ValueError("OFFERING_NOT_AVAILABLE")
            player = db.get(PlayerProfile, offering.player_id)
            if (
                not player
                or player.verification_status != "APPROVED"
                or player.service_status != "AVAILABLE"
            ):
                raise ValueError("PLAYER_NOT_AVAILABLE")
            if player.user_id == user_id:
                raise ValueError("CANNOT_ORDER_OWN_OFFERING")
            sku = db.get(ServiceSKU, offering.sku_id)
            designated_player_id = player.id
            unit_price = offering.price_override if offering.price_override is not None else sku.price
        else:
            sku = db.get(ServiceSKU, sku_id)
            unit_price = sku.price if sku else 0

        if not sku or sku.status != "ACTIVE":
            raise ValueError("SKU_NOT_AVAILABLE")
        game = db.get(Game, sku.game_id)
        if not game or game.status != "ACTIVE":
            raise ValueError("GAME_NOT_AVAILABLE")

        total = unit_price * quantity
        platform_fee = int(total * float(sku.platform_fee_rate))
        order = Order(
            order_no=f"ORD_{uuid.uuid4().hex[:20].upper()}",
            user_id=user_id,
            game_id=sku.game_id,
            sku_id=sku.id,
            designated_player_id=designated_player_id,
            status=OrderStatus.WAITING_PAYMENT.value,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total,
            player_amount=total - platform_fee,
            platform_fee=platform_fee,
            remark=remark,
        )
        db.add(order)
        db.flush()
        OrderService._record(
            db,
            order,
            "ORDER_CREATED",
            None,
            OrderStatus.WAITING_PAYMENT.value,
            "USER",
            str(user_id),
            {
                "designatedPlayerId": str(designated_player_id)
                if designated_player_id
                else None
            },
        )
        db.commit()
        return order

    @staticmethod
    def get(db: Session, order_id: uuid.UUID) -> Order:
        order = db.get(Order, order_id)
        if not order:
            raise OrderNotFound(str(order_id))
        return order

    @staticmethod
    def transition(
        db: Session,
        order: Order,
        target: OrderStatus,
        *,
        event_type: str,
        actor_type: str,
        actor_id: str | None = None,
        payload: dict | None = None,
    ) -> Order:
        ensure_transition(order.status, target.value)
        previous = order.status
        order.status = target.value
        order.version += 1
        now = datetime.now(timezone.utc)
        if target == OrderStatus.PAID:
            order.paid_at = now
        elif target == OrderStatus.ACCEPTED:
            order.accepted_at = now
        elif target == OrderStatus.IN_SERVICE:
            order.service_started_at = now
        elif target == OrderStatus.FINISH_REQUESTED:
            order.finish_requested_at = now
        elif target == OrderStatus.COMPLETED:
            order.completed_at = now
        elif target == OrderStatus.SETTLED:
            order.settled_at = now
        OrderService._record(
            db,
            order,
            event_type,
            previous,
            target.value,
            actor_type,
            actor_id,
            payload or {},
        )
        observe_order_transition(
            from_status=previous,
            to_status=target.value,
            event_type=event_type,
        )
        return order

    @staticmethod
    def cancel(db: Session, order: Order, user_id: uuid.UUID) -> Order:
        locked_order = db.scalar(
            select(Order).where(Order.id == order.id).with_for_update()
        )
        if not locked_order:
            raise OrderNotFound(str(order.id))
        if locked_order.user_id != user_id:
            raise PermissionError("ORDER_NOT_OWNED")
        OrderService.transition(
            db,
            locked_order,
            OrderStatus.CANCELLED,
            event_type="ORDER_CANCELLED",
            actor_type="USER",
            actor_id=str(user_id),
        )
        db.commit()
        return locked_order

    @staticmethod
    def _record(
        db: Session,
        order: Order,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        actor_type: str,
        actor_id: str | None,
        payload: dict,
    ) -> None:
        db.add(
            OrderEvent(
                order_id=order.id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                actor_type=actor_type,
                actor_id=actor_id,
                payload_json=payload,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            OutboxEvent(
                aggregate_type="ORDER",
                aggregate_id=str(order.id),
                event_type=event_type,
                payload_json={"orderId": str(order.id), "status": to_status, **payload},
            )
        )

