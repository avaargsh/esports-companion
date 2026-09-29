from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import SessionLocal
from app.infrastructure import redis_client
from app.providers.registry import get_wechat_callback_verifier
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/wechat/callback")
async def wechat_payment_callback(request: Request):
    body = await request.body()
    try:
        verifier = get_wechat_callback_verifier()
        callback = verifier.verify_and_decrypt(
            headers=request.headers,
            body=body,
        )
        with SessionLocal() as db:
            result = PaymentService.apply_verified_success(
                db,
                callback=callback,
            )
            if result.order.status == "MATCHING":
                try:
                    redis_client.zadd(
                        f"order_pool:{result.order.game_id}",
                        {
                            str(result.order.id):
                            result.order.created_at.timestamp()
                        },
                    )
                except Exception:
                    pass
        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "成功"},
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": str(exc)},
        )
