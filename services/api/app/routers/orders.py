import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.infrastructure import redis_client
from app.models import Order
from app.schemas import OrderCreate, OrderOut, PaymentPrepareOut
from app.providers.registry import get_payment_provider
from app.services.completion_service import CompletionService
from app.services.order_service import OrderNotFound, OrderService
from app.services.payment_service import PaymentService
from app.security import Principal, current_principal, current_user_id

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
def list_orders(
    user_id: uuid.UUID = Depends(current_user_id),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
    )


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    body: OrderCreate,
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    try:
        return OrderService.create_order(
            db,
            user_id=user_id,
            sku_id=body.sku_id,
            offering_id=body.offering_id,
            quantity=body.quantity,
            remark=body.remark,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        if order.user_id == principal.user_id or "PLATFORM" in principal.roles:
            return order

        if "PLAYER" in principal.roles:
            from app.models import OrderAssignment, PlayerProfile

            player = db.scalar(
                select(PlayerProfile).where(
                    PlayerProfile.user_id == principal.user_id
                )
            )
            if player:
                assignment = db.scalar(
                    select(OrderAssignment).where(
                        OrderAssignment.order_id == order.id,
                        OrderAssignment.player_id == player.id,
                        OrderAssignment.status == "ACTIVE",
                    )
                )
                if assignment:
                    return order
        raise PermissionError("ORDER_ACCESS_DENIED")
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/{order_id}/payments", response_model=PaymentPrepareOut)
def prepare_payment(
    order_id: uuid.UUID,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        if order.user_id != user_id:
            raise PermissionError("ORDER_NOT_OWNED")

        provider = get_payment_provider()
        preparation = PaymentService.prepare_payment(
            db,
            order=order,
            provider=provider,
            idempotency_key=idempotency_key,
        )
        return PaymentPrepareOut(
            order_id=order.id,
            order_status=order.status,
            provider=preparation.transaction.provider,
            payment_status=preparation.transaction.status,
            client_payload=preparation.client_payload,
            replayed=preparation.replayed,
        )
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        if (
            message.startswith("PAYMENT_PROVIDER_NOT_CONFIGURED")
            or message.startswith("WECHAT_PAYMENT_CREDENTIALS_MISSING")
        ):
            raise HTTPException(503, message) from exc
        raise HTTPException(409, message) from exc


@router.post("/{order_id}/mock-pay", response_model=OrderOut)
def mock_pay(
    order_id: uuid.UUID,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    try:
        from app.config import settings

        if settings.app_env.lower() in {"prod", "production"}:
            raise PermissionError("MOCK_PAYMENT_DISABLED")
        order = OrderService.get(db, order_id)
        if order.user_id != user_id:
            raise PermissionError("ORDER_NOT_OWNED")
        order = PaymentService.create_payment(
            db,
            order=order,
            provider=get_payment_provider("mock"),
            idempotency_key=idempotency_key,
        )
        try:
            redis_client.zadd(
                f"order_pool:{order.game_id}",
                {str(order.id): order.created_at.timestamp()},
            )
        except Exception:
            pass
        return order
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        order = OrderService.cancel(db, order, user_id)
        try:
            redis_client.zrem(f"order_pool:{order.game_id}", str(order.id))
        except Exception:
            pass
        return order
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    try:
        return CompletionService.confirm_by_user(
            db,
            order_id=order_id,
            user_id=user_id,
        )
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, LookupError) as exc:
        raise HTTPException(409, str(exc)) from exc
