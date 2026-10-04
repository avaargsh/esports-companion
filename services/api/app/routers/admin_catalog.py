import base64
import binascii
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Game, ServiceSKU
from app.providers.object_storage import MinIOImageStorage
from app.schemas import (
    GameAdminCreate,
    GameAdminUpdate,
    SKUAdminCreate,
    SKUAdminUpdate,
)
from app.security import Principal, require_platform
from app.status_labels import COMMON_STATUS_TEXT, status_text

router = APIRouter(prefix="/api/v1/admin/catalog", tags=["admin-catalog"])


class CatalogImageUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=128)
    data_base64: str = Field(min_length=1)


def _storage() -> MinIOImageStorage:
    return MinIOImageStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket_name=settings.minio_bucket_name,
        secure=settings.minio_secure,
        public_url=settings.minio_public_url,
    )


def _validate_status(status: str) -> str:
    value = status.upper()
    if value not in {"ACTIVE", "INACTIVE", "DELETED"}:
        raise HTTPException(409, "INVALID_CATALOG_STATUS")
    return value


@router.post("/images", status_code=201)
def upload_catalog_image(
    body: CatalogImageUpload,
    principal: Principal = Depends(require_platform),
):
    try:
        content = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "INVALID_IMAGE_DATA") from exc
    if not content:
        raise HTTPException(400, "EMPTY_IMAGE")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "IMAGE_TOO_LARGE")
    try:
        storage = _storage()
        key = storage.upload_image_bytes(
            filename=body.filename,
            content=content,
            content_type=body.content_type,
        )
        return {"key": key, "url": storage.get_public_url(key)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/games")
def list_games(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    games = list(
        db.scalars(
            select(Game)
            .where(Game.status != "DELETED")
            .order_by(Game.sort_order, Game.created_at)
        )
    )
    return [
        {
            "id": str(game.id),
            "code": game.code,
            "name": game.name,
            "iconUrl": game.icon_url,
            "status": status_text(game.status, COMMON_STATUS_TEXT),
            "statusCode": game.status,
            "sortOrder": game.sort_order,
        }
        for game in games
    ]


@router.post("/games", status_code=201)
def create_game(
    body: GameAdminCreate,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    game = Game(
        code=body.code,
        name=body.name,
        icon_url=body.icon_url,
        status="ACTIVE",
        sort_order=body.sort_order,
    )
    db.add(game)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "GAME_CODE_ALREADY_EXISTS") from exc
    db.refresh(game)
    return {
        "id": str(game.id),
        "code": game.code,
        "name": game.name,
        "iconUrl": game.icon_url,
        "status": status_text(game.status, COMMON_STATUS_TEXT),
            "statusCode": game.status,
        "sortOrder": game.sort_order,
    }


@router.patch("/games/{game_id}")
def update_game(
    game_id: uuid.UUID,
    body: GameAdminUpdate,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    if not game or game.status == "DELETED":
        raise HTTPException(404, "GAME_NOT_FOUND")
    if body.name is not None:
        game.name = body.name
    if body.icon_url is not None:
        game.icon_url = body.icon_url
    if body.sort_order is not None:
        game.sort_order = body.sort_order
    if body.status is not None:
        game.status = _validate_status(body.status)
    db.commit()
    db.refresh(game)
    return {
        "id": str(game.id),
        "code": game.code,
        "name": game.name,
        "iconUrl": game.icon_url,
        "status": status_text(game.status, COMMON_STATUS_TEXT),
            "statusCode": game.status,
        "sortOrder": game.sort_order,
    }


@router.delete("/games/{game_id}")
def delete_game(
    game_id: uuid.UUID,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    if not game or game.status == "DELETED":
        raise HTTPException(404, "GAME_NOT_FOUND")
    game.status = "DELETED"
    skus = list(db.scalars(select(ServiceSKU).where(ServiceSKU.game_id == game.id)))
    for sku in skus:
        sku.status = "INACTIVE"
    db.commit()
    return {"id": str(game.id), "status": status_text(game.status, COMMON_STATUS_TEXT), "statusCode": game.status}


@router.get("/skus")
def list_skus(
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    rows = list(
        db.execute(
            select(ServiceSKU, Game)
            .join(Game, Game.id == ServiceSKU.game_id)
            .where(Game.status != "DELETED")
            .order_by(Game.sort_order, ServiceSKU.created_at)
        )
    )
    return [
        {
            "id": str(sku.id),
            "gameId": str(sku.game_id),
            "gameName": game.name,
            "name": sku.name,
            "serviceType": sku.service_type,
            "unit": sku.unit,
            "durationMinutes": sku.duration_minutes,
            "price": sku.price,
            "platformFeeRate": float(sku.platform_fee_rate),
            "status": status_text(sku.status, COMMON_STATUS_TEXT),
            "statusCode": sku.status,
            "config": sku.config_json,
        }
        for sku, game in rows
    ]


@router.post("/skus", status_code=201)
def create_sku(
    body: SKUAdminCreate,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    game = db.get(Game, body.game_id)
    if not game or game.status == "DELETED":
        raise HTTPException(404, "GAME_NOT_FOUND")
    sku = ServiceSKU(
        game_id=game.id,
        name=body.name,
        service_type=body.service_type,
        unit=body.unit,
        duration_minutes=body.duration_minutes,
        price=body.price,
        platform_fee_rate=body.platform_fee_rate,
        status=_validate_status(body.status),
        config_json=body.config_json,
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return {"id": str(sku.id), "status": status_text(sku.status, COMMON_STATUS_TEXT), "statusCode": sku.status}


@router.patch("/skus/{sku_id}")
def update_sku(
    sku_id: uuid.UUID,
    body: SKUAdminUpdate,
    principal: Principal = Depends(require_platform),
    db: Session = Depends(get_db),
):
    sku = db.get(ServiceSKU, sku_id)
    if not sku:
        raise HTTPException(404, "SKU_NOT_FOUND")
    for field in (
        "name",
        "service_type",
        "unit",
        "duration_minutes",
        "price",
        "platform_fee_rate",
        "config_json",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(sku, field, value)
    if body.status is not None:
        sku.status = _validate_status(body.status)
    db.commit()
    db.refresh(sku)
    return {"id": str(sku.id), "status": status_text(sku.status, COMMON_STATUS_TEXT), "statusCode": sku.status}
