import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Review
from app.services.dispatch_service import DispatchService
from app.services.order_authorization_policy import OrderAuthorizationPolicy
from app.services.order_service import OrderNotFound, OrderService
from app.security import current_user_id

router = APIRouter(prefix="/api/v1/orders", tags=["reviews"])


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    content: str = Field(default="", max_length=1000)


@router.post("/{order_id}/reviews", status_code=201)
def create_review(
    order_id: uuid.UUID,
    body: ReviewCreate,
    user_id: uuid.UUID = Depends(current_user_id),
    db: Session = Depends(get_db),
):
    try:
        order = OrderService.get(db, order_id)
        OrderAuthorizationPolicy.require_owner(order, user_id=user_id)
        if order.status != "SETTLED":
            raise ValueError("ORDER_NOT_SETTLED")
        assignment = DispatchService.active_assignment(db, order.id)
        review = Review(
            order_id=order.id,
            user_id=user_id,
            player_id=assignment.player_id,
            rating=body.rating,
            content=body.content,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return {
            "id": str(review.id),
            "orderId": str(review.order_id),
            "rating": review.rating,
            "content": review.content,
        }
    except OrderNotFound as exc:
        raise HTTPException(404, "ORDER_NOT_FOUND") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "ORDER_ALREADY_REVIEWED") from exc
