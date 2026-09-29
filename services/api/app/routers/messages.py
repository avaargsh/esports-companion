import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import OrderMessageCreate, OrderMessageOut
from app.security import Principal, current_principal
from app.services.order_messaging_service import OrderMessagingService
from app.services.order_service import OrderNotFound, OrderService

router = APIRouter(prefix="/api/v1/orders", tags=["messages"])


@router.get("/{order_id}/messages", response_model=list[OrderMessageOut])
def list_messages(
    order_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        return OrderMessagingService.list_messages(
            db,
            order=order,
            user_id=principal.user_id,
            roles=principal.roles,
            limit=limit,
        )
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post(
    "/{order_id}/messages",
    response_model=OrderMessageOut,
    status_code=201,
)
def create_message(
    order_id: uuid.UUID,
    body: OrderMessageCreate,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        return OrderMessagingService.create_message(
            db,
            order=order,
            user_id=principal.user_id,
            roles=principal.roles,
            client_message_id=body.client_message_id.strip(),
            content=body.content,
        )
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
