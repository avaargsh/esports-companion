from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db import SessionLocal
from app.infrastructure import redis_client

router = APIRouter(tags=["health"])


def dependency_status() -> tuple[bool, bool]:
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
    return db_ok, redis_ok


def readiness_payload() -> tuple[dict, bool]:
    db_ok, redis_ok = dependency_status()
    ready = db_ok and (redis_ok or not settings.readiness_require_redis)
    return (
        {
            "status": "ready" if ready else "not_ready",
            "service": settings.service_name,
            "environment": settings.app_env,
            "commit": settings.commit_sha,
            "dependencies": {
                "postgres": db_ok,
                "redis": redis_ok,
            },
        },
        ready,
    )


@router.get("/livez")
def livez():
    return {
        "status": "alive",
        "service": settings.service_name,
        "environment": settings.app_env,
        "commit": settings.commit_sha,
    }


@router.get("/readyz")
def readyz():
    payload, ready = readiness_payload()
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@router.get("/health")
def health():
    payload, ready = readiness_payload()
    payload["status"] = "ok" if ready else "degraded"
    return JSONResponse(status_code=200 if ready else 503, content=payload)
