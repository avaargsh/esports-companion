from fastapi import FastAPI
from sqlalchemy import text

from app.db import SessionLocal
from app.infrastructure import redis_client
from app.routers.catalog import router as catalog_router
from app.routers.orders import router as orders_router
from app.routers.player import router as player_router

app = FastAPI(title="esports-companion API", version="0.1.0")
app.include_router(catalog_router)
app.include_router(orders_router)
app.include_router(player_router)


@app.get("/health")
def health():
    db_ok = False
    redis_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
            db_ok = True
    except Exception:
        pass
    try:
        redis_ok = bool(redis_client.ping())
    except Exception:
        pass
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "postgres": db_ok,
        "redis": redis_ok,
    }
