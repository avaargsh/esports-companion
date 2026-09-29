import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.infrastructure import redis_client
from app.schemas import OrderCreate, OrderOut
from app.services.order_service import MockPaymentService, OrderNotFound, OrderService

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def demo_user_id(x_user_id: uuid.UUID = Header(alias="X-User-Id")) -> uuid.UUID:
    return x_user_id


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    body: OrderCreate,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    try:
        return OrderService.create_order(
            db,
            user_id=user_id,
            sku_id=body.sku_id,
            quantity=body.quantity,
            remark=body.remark,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return OrderService.get(db, order_id)
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc


@router.post("/{order_id}/mock-pay", response_model=OrderOut)
def mock_pay(
    order_id: uuid.UUID,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        order = MockPaymentService.pay(db, order, idempotency_key)
        redis_client.zadd(
            f"order_pool:{order.game_id}",
            {str(order.id): order.created_at.timestamp()},
        )
        return order
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(demo_user_id),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        order = OrderService.cancel(db, order, user_id)
        redis_client.zrem(f"order_pool:{order.game_id}", str(order.id))
        return order
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
