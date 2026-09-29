import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Dispute, Refund
from app.schemas import DisputeOut, RefundComplete, RefundOut
from app.security import Principal, require_platform
from app.services.dispute_service import DisputeService

router = APIRouter(prefix="/api/v1/admin", tags=["admin-disputes"])


@router.get("/disputes", response_model=list[DisputeOut])
def list_disputes(
    status: str | None = Query(default=None),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    stmt = select(Dispute).order_by(Dispute.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(Dispute.status == status.upper())
    return list(db.scalars(stmt))


@router.post("/disputes/{dispute_id}/release", response_model=DisputeOut)
def release_to_provider(
    dispute_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        return DisputeService.release_to_provider(
            db,
            dispute_id=dispute_id,
            admin_user_id=principal.user_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/disputes/{dispute_id}/refund", response_model=RefundOut)
def approve_refund(
    dispute_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        return DisputeService.approve_refund(
            db,
            dispute_id=dispute_id,
            admin_user_id=principal.user_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/refunds", response_model=list[RefundOut])
def list_refunds(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Refund)
            .order_by(Refund.created_at.desc())
            .limit(100)
        )
    )


@router.post("/refunds/{refund_id}/complete", response_model=RefundOut)
def complete_refund(
    refund_id: uuid.UUID,
    body: RefundComplete,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        return DisputeService.complete_refund(
            db,
            refund_id=refund_id,
            provider_refund_id=body.provider_refund_id,
            admin_user_id=principal.user_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
