import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Dispute, Order
from app.schemas import DisputeCreate, DisputeOut
from app.security import Principal, current_principal
from app.services.dispute_service import DisputeService
from app.services.order_authorization_policy import OrderAuthorizationPolicy
from app.services.order_service import OrderNotFound

router = APIRouter(prefix="/api/v1/orders", tags=["disputes"])


@router.post("/{order_id}/disputes", response_model=DisputeOut, status_code=201)
def open_dispute(
    order_id: uuid.UUID,
    body: DisputeCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    try:
        return DisputeService.open(
            db,
            order_id=order_id,
            actor_user_id=principal.user_id,
            actor_roles=principal.roles,
            reason_code=body.reason_code,
            description=body.description,
            idempotency_key=idempotency_key,
        )
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{order_id}/disputes", response_model=DisputeOut)
def get_dispute(
    order_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "ORDER_NOT_FOUND")
    try:
        OrderAuthorizationPolicy.require_viewer(
            db,
            order=order,
            user_id=principal.user_id,
            roles=principal.roles,
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc

    dispute = db.scalar(select(Dispute).where(Dispute.order_id == order_id))
    if not dispute:
        raise HTTPException(404, "DISPUTE_NOT_FOUND")
    return dispute
