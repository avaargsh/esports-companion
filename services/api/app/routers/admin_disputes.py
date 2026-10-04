import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Dispute, OrderAssignment, Refund
from app.schemas import DisputeOut, RefundComplete, RefundOut
from app.providers.registry import get_refund_provider
from app.security import Principal, require_platform
from app.services.dispute_service import DisputeService
from app.services.refund_service import RefundService

router = APIRouter(prefix="/api/v1/admin", tags=["admin-disputes"])


def _dispute_out(db: Session, dispute: Dispute) -> dict:
    payload = DisputeOut.model_validate(dispute).model_dump()
    actions: list[str] = []
    if dispute.status == "OPEN":
        actions.append("REFUND_CUSTOMER")
        has_active_provider = db.scalar(
            select(OrderAssignment.id).where(
                OrderAssignment.order_id == dispute.order_id,
                OrderAssignment.status == "ACTIVE",
            )
        )
        if has_active_provider:
            actions.insert(0, "RELEASE_PROVIDER")
    payload["available_actions"] = actions
    return payload


@router.get("/disputes", response_model=list[DisputeOut])
def list_disputes(
    status: str | None = Query(default=None),
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    stmt = select(Dispute).order_by(Dispute.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(Dispute.status == status.upper())
    return [_dispute_out(db, item) for item in db.scalars(stmt)]


@router.post("/disputes/{dispute_id}/release", response_model=DisputeOut)
def release_to_provider(
    dispute_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        dispute = DisputeService.release_to_provider(
            db,
            dispute_id=dispute_id,
            admin_user_id=principal.user_id,
        )
        return _dispute_out(db, dispute)
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
        refund = DisputeService.approve_refund(
            db,
            dispute_id=dispute_id,
            admin_user_id=principal.user_id,
        )
        return RefundService.submit(
            db,
            refund_id=refund.id,
            provider=get_refund_provider(),
            actor_user_id=principal.user_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/refunds/{refund_id}/submit", response_model=RefundOut)
def submit_refund(
    refund_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        return RefundService.submit(
            db,
            refund_id=refund_id,
            provider=get_refund_provider(),
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/refunds/{refund_id}/reconcile", response_model=RefundOut)
def reconcile_refund(
    refund_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    try:
        return RefundService.reconcile(
            db,
            refund_id=refund_id,
            provider=get_refund_provider(),
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
        refund = db.get(Refund, refund_id)
        if not refund:
            raise LookupError("REFUND_NOT_FOUND")
        if refund.provider != "MANUAL":
            raise ValueError("PROVIDER_REFUND_MUST_BE_RECONCILED")
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
