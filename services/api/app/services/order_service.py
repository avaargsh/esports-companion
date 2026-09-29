import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus, ensure_transition
from app.models import Order, OrderEvent, OutboxEvent, ServiceSKU


class OrderNotFound(LookupError):
    pass


class OrderService:
    @staticmethod
    def create_order(
        db: Session,
        *,
        user_id: uuid.UUID,
        sku_id: uuid.UUID,
        quantity: int = 1,
        remark: str = "",
    ) -> Order:
        sku = db.get(ServiceSKU, sku_id)
        if not sku or sku.status != "ACTIVE":
            raise ValueError("SKU_NOT_AVAILABLE")
        total = sku.price * quantity
        platform_fee = int(total * float(sku.platform_fee_rate))
        order = Order(
            order_no=f"ORD_{uuid.uuid4().hex[:20].upper()}",
            user_id=user_id,
            game_id=sku.game_id,
            sku_id=sku.id,
            status=OrderStatus.WAITING_PAYMENT.value,
            quantity=quantity,
            unit_price=sku.price,
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
            {},
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
        return order

    @staticmethod
    def cancel(db: Session, order: Order, user_id: uuid.UUID) -> Order:
        if order.user_id != user_id:
            raise PermissionError("ORDER_NOT_OWNED")
        OrderService.transition(
            db,
            order,
            OrderStatus.CANCELLED,
            event_type="ORDER_CANCELLED",
            actor_type="USER",
            actor_id=str(user_id),
        )
        db.commit()
        return order

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

