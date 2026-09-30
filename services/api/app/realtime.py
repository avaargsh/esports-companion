import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Order, OrderAssignment, OutboxEvent, PlayerProfile


class ConnectionManager:
    def __init__(self):
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._subscriptions: dict[WebSocket, set[str]] = defaultdict(set)
        self._identities: dict[WebSocket, tuple[str, tuple[str, ...]]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        *,
        user_id: uuid.UUID,
        roles: tuple[str, ...],
    ) -> None:
        await websocket.accept()
        self._identities[websocket] = (str(user_id), roles)

    def subscribe(self, websocket: WebSocket, channels: list[str]) -> list[str]:
        accepted = []
        for channel in channels[:20]:
            if not (channel.startswith("order:") or channel.startswith("user:")):
                continue
            self._channels[channel].add(websocket)
            self._subscriptions[websocket].add(channel)
            accepted.append(channel)
        return accepted

    def disconnect(self, websocket: WebSocket) -> None:
        self._identities.pop(websocket, None)
        for channel in self._subscriptions.pop(websocket, set()):
            sockets = self._channels.get(channel)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    self._channels.pop(channel, None)

    async def publish(
        self,
        channels: list[str],
        message: dict,
        *,
        order_allowed_user_ids: set[str] | None = None,
    ) -> None:
        targets: set[WebSocket] = set()
        for channel in channels:
            sockets = self._channels.get(channel, set())
            if channel.startswith("order:") and order_allowed_user_ids is not None:
                for websocket in sockets:
                    identity = self._identities.get(websocket)
                    if not identity:
                        continue
                    user_id, roles = identity
                    if user_id in order_allowed_user_ids or "PLATFORM" in roles:
                        targets.add(websocket)
                continue
            targets.update(sockets)

        dead = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()


def _load_pending(limit: int = 50) -> list[dict]:
    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING")
                .order_by(OutboxEvent.created_at)
                .limit(limit)
            )
        )
        result = []
        for event in events:
            user_id = None
            order_allowed_user_ids: set[str] = set()
            if event.aggregate_type == "ORDER":
                try:
                    order = db.get(Order, uuid.UUID(event.aggregate_id))
                except ValueError:
                    order = None
                if order:
                    user_id = str(order.user_id)
                    order_allowed_user_ids.add(user_id)
                    active_player_user_id = db.scalar(
                        select(PlayerProfile.user_id)
                        .join(
                            OrderAssignment,
                            OrderAssignment.player_id == PlayerProfile.id,
                        )
                        .where(
                            OrderAssignment.order_id == order.id,
                            OrderAssignment.status == "ACTIVE",
                        )
                    )
                    if active_player_user_id:
                        order_allowed_user_ids.add(str(active_player_user_id))
            result.append(
                {
                    "id": str(event.id),
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": event.aggregate_id,
                    "event_type": event.event_type,
                    "payload": event.payload_json,
                    "user_id": user_id,
                    "order_allowed_user_ids": order_allowed_user_ids,
                }
            )
        return result


def _mark_published(event_ids: list[str]) -> None:
    if not event_ids:
        return
    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.id.in_([uuid.UUID(value) for value in event_ids])
                )
            )
        )
        now = datetime.now(timezone.utc)
        for event in events:
            event.status = "PUBLISHED"
            event.published_at = now
        db.commit()


async def run_outbox_publisher() -> None:
    while True:
        events = await asyncio.to_thread(_load_pending)
        published = []
        for event in events:
            if event["aggregate_type"] != "ORDER":
                published.append(event["id"])
                continue

            channels = [f"order:{event['aggregate_id']}"]
            if event["user_id"]:
                channels.append(f"user:{event['user_id']}")
            message_type = (
                "order.message_created"
                if event["event_type"] == "ORDER_MESSAGE_CREATED"
                else "order.status_changed"
            )
            await manager.publish(
                channels,
                {
                    "type": message_type,
                    "eventId": event["id"],
                    "eventType": event["event_type"],
                    **event["payload"],
                },
                order_allowed_user_ids=event["order_allowed_user_ids"],
            )
            published.append(event["id"])
        await asyncio.to_thread(_mark_published, published)
        await asyncio.sleep(0.5)
