from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import SessionLocal
from app.providers.registry import get_wechat_refund_callback_verifier
from app.services.refund_service import RefundService

router = APIRouter(prefix="/api/v1/refunds", tags=["refunds"])


@router.post("/wechat/callback")
async def wechat_refund_callback(request: Request):
    body = await request.body()
    try:
        verifier = get_wechat_refund_callback_verifier()
        callback = verifier.verify_and_decrypt(headers=request.headers, body=body)
        with SessionLocal() as db:
            RefundService.apply_wechat_callback(db, callback=callback)
        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "成功"},
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": str(exc)},
        )
