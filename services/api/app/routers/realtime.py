from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "subscribe":
                await websocket.send_json(
                    {"type": "error", "code": "UNSUPPORTED_MESSAGE_TYPE"}
                )
                continue
            channels = message.get("channels") or []
            accepted = manager.subscribe(websocket, channels)
            await websocket.send_json(
                {
                    "type": "subscribed",
                    "channels": accepted,
                }
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
