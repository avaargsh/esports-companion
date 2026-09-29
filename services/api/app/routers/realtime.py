import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Order, User
from app.realtime import manager
from app.services.order_messaging_service import OrderMessagingService
from app.services.session_service import SessionService

router = APIRouter(tags=["realtime"])


def _authenticate_websocket(
    websocket: WebSocket,
    db: Session,
) -> tuple[uuid.UUID, tuple[str, ...]] | None:
    authorization = websocket.headers.get("authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            user, _session, roles = SessionService.authenticate_access(
                db,
                access_token=token,
            )
        except ValueError:
            return None
        return user.id, roles

    if not settings.is_production:
        raw_user_id = websocket.query_params.get("user_id")
        if raw_user_id:
            try:
                user_id = uuid.UUID(raw_user_id)
            except ValueError:
                return None
            user = db.get(User, user_id)
            if user and user.status == "ACTIVE":
                return user.id, SessionService.roles_for_user(db, user)

    return None


def _authorized_channels(
    db: Session,
    *,
    user_id: uuid.UUID,
    roles: tuple[str, ...],
    channels: list[str],
) -> tuple[list[str], list[str]]:
    accepted: list[str] = []
    rejected: list[str] = []

    for channel in channels[:20]:
        if channel.startswith("user:"):
            raw_id = channel.removeprefix("user:")
            try:
                channel_user_id = uuid.UUID(raw_id)
            except ValueError:
                rejected.append(channel)
                continue
            if channel_user_id == user_id or "PLATFORM" in roles:
                accepted.append(channel)
            else:
                rejected.append(channel)
            continue

        if channel.startswith("order:"):
            raw_id = channel.removeprefix("order:")
            try:
                order_id = uuid.UUID(raw_id)
            except ValueError:
                rejected.append(channel)
                continue
            order = db.get(Order, order_id)
            if not order:
                rejected.append(channel)
                continue
            try:
                OrderMessagingService.participant_role(
                    db,
                    order=order,
                    user_id=user_id,
                    roles=roles,
                )
                accepted.append(channel)
            except PermissionError:
                rejected.append(channel)
            continue

        rejected.append(channel)

    return accepted, rejected


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    with SessionLocal() as db:
        identity = _authenticate_websocket(websocket, db)
    if identity is None:
        await websocket.close(code=4401)
        return

    user_id, roles = identity
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "subscribe":
                await websocket.send_json(
                    {"type": "error", "code": "UNSUPPORTED_MESSAGE_TYPE"}
                )
                continue

            requested = message.get("channels") or []
            if not isinstance(requested, list):
                await websocket.send_json(
                    {"type": "error", "code": "CHANNELS_REQUIRED"}
                )
                continue

            with SessionLocal() as db:
                accepted, rejected = _authorized_channels(
                    db,
                    user_id=user_id,
                    roles=roles,
                    channels=[str(item) for item in requested],
                )
            manager.subscribe(websocket, accepted)
            await websocket.send_json(
                {
                    "type": "subscribed",
                    "channels": accepted,
                    "rejected": rejected,
                }
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
