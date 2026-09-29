import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.infrastructure import redis_client
from app.realtime import run_outbox_publisher
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.catalog import router as catalog_router
from app.routers.dev import router as dev_router
from app.routers.orders import router as orders_router
from app.routers.payments import router as payments_router
from app.routers.player import router as player_router
from app.routers.realtime import router as realtime_router
from app.routers.reviews import router as reviews_router
from app.routers.wallet import router as wallet_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_outbox_publisher())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="esports-companion API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(player_router)
app.include_router(wallet_router)
app.include_router(reviews_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(dev_router)
app.include_router(realtime_router)


@app.get("/health")
def health():
    db_ok = False
    redis_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
            db_ok = True
    except SQLAlchemyError:
        db_ok = False
    try:
        redis_ok = bool(redis_client.ping())
    except RedisError:
        redis_ok = False
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "postgres": db_ok,
        "redis": redis_ok,
    }
