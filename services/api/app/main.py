import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from dataclasses import replace

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import SessionLocal

from app.health import router as health_router
from app.metrics import router as metrics_router
from app.observability import RequestLoggingMiddleware, configure_logging
from app.operational_metrics import run_operational_metrics_worker
from app.telemetry import configure_tracing
from app.order_timeout import run_timeout_scanner
from app.realtime import run_outbox_publisher
from app.refund_reconcile import run_refund_reconcile_worker
from app.routers.admin import router as admin_router
from app.routers.admin_catalog import router as admin_catalog_router
from app.routers.auth import router as auth_router
from app.routers.catalog import router as catalog_router
from app.routers.dev import router as dev_router
from app.routers.disputes import router as disputes_router
from app.routers.admin_disputes import router as admin_disputes_router
from app.routers.orders import router as orders_router
from app.routers.messages import router as messages_router
from app.routers.minio import router as minio_router
from app.routers.payments import router as payments_router
from app.routers.player import router as player_router
from app.routers.offerings import router as offerings_router
from app.routers.realtime import router as realtime_router
from app.routers.reviews import router as reviews_router
from app.routers.user_wechat import router as user_wechat_router
from app.routers.refunds import router as refunds_router
from app.routers.wallet import router as wallet_router
from app.routers.marketplace import router as marketplace_router
from app.routers.withdrawals import router as withdrawals_router
from app.services.authorization_audit import AuthorizationAudit
from app.services.authority_admission import AuthorityAdmissionDenied
from app.services.resource_authorization_policy import ResourceAuthorizationDenied


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(run_outbox_publisher()),
        asyncio.create_task(run_timeout_scanner()),
        asyncio.create_task(run_refund_reconcile_worker()),
        asyncio.create_task(run_operational_metrics_worker()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


configure_logging()
configure_tracing()

app = FastAPI(
    title="esports-companion API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_api_docs else None,
    redoc_url="/redoc" if settings.expose_api_docs else None,
    openapi_url="/openapi.json" if settings.expose_api_docs else None,
)


@app.exception_handler(AuthorityAdmissionDenied)
async def authority_admission_denied(
    request: Request,
    exc: AuthorityAdmissionDenied,
):
    try:
        with SessionLocal() as db:
            AuthorizationAudit.record_admission(
                db,
                authority=exc.authority,
                admission=exc.admission,
            )
            db.commit()
    except Exception:
        logging.getLogger("authorization.audit").exception(
            "failed to persist denied authority admission",
            extra={
                "request_id": exc.authority.authorization.request_id,
                "authority_digest": exc.authority.digest,
            },
        )

    return JSONResponse(
        status_code=409,
        content={"detail": exc.admission.reason_code},
    )


@app.exception_handler(ResourceAuthorizationDenied)
async def resource_authorization_denied(
    request: Request,
    exc: ResourceAuthorizationDenied,
):
    decision = exc.decision
    if decision.request_id is None:
        decision = replace(
            decision,
            request_id=getattr(request.state, "request_id", None),
        )

    try:
        with SessionLocal() as db:
            AuthorizationAudit.record(db, decision=decision)
            db.commit()
    except Exception:
        logging.getLogger("authorization.audit").exception(
            "failed to persist denied authorization decision",
            extra={"request_id": decision.request_id},
        )

    return JSONResponse(
        status_code=403,
        content={"detail": decision.reason_code},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(marketplace_router)
app.include_router(orders_router)
app.include_router(messages_router)
app.include_router(minio_router)
app.include_router(disputes_router)
app.include_router(payments_router)
app.include_router(refunds_router)
app.include_router(player_router)
app.include_router(offerings_router)
app.include_router(wallet_router)
app.include_router(withdrawals_router)
app.include_router(reviews_router)
app.include_router(admin_router)
app.include_router(admin_disputes_router)
app.include_router(admin_catalog_router)
app.include_router(auth_router)
app.include_router(user_wechat_router)
if not settings.is_secure_deployment:
    app.include_router(dev_router)
app.include_router(realtime_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.add_middleware(RequestLoggingMiddleware)
