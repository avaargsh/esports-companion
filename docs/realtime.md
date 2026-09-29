# Realtime

v0.1 exposes one WebSocket endpoint:

```text
/ws
```

Subscribe:

```json
{
  "type": "subscribe",
  "channels": ["user:<user-id>", "order:<order-id>"]
}
```

Order domain events are written to PostgreSQL `outbox_events` in the same transaction as the order state change. A lightweight in-process publisher delivers pending events to WebSocket subscribers and marks them published.

This is intentionally a single-instance v0.1 implementation. Production multi-instance delivery should move the outbox consumer to a dedicated worker or use Redis Streams / a message broker while PostgreSQL remains the durable source of truth.

Production authentication must authorize channel subscriptions. Demo mode keeps the protocol intentionally simple.
