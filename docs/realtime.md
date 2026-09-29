# Realtime

The API exposes one authenticated WebSocket endpoint:

```text
/ws
```

Development/demo clients may identify with:

```text
/ws?user_id=<demo-user-uuid>
```

That compatibility path is disabled in production. Production WebSocket
connections must send the same Bearer access token used by HTTP APIs in the
`Authorization` header.

Subscribe after the socket opens:

```json
{
  "type": "subscribe",
  "channels": ["user:<user-id>", "order:<order-id>"]
}
```

Subscriptions are authorized server-side. A user channel is limited to the
authenticated user (or PLATFORM). An order channel is limited to the customer,
PLATFORM, or a player who has an assignment history for that order. Rejected
channels are returned explicitly and are never registered with the connection
manager.

Order domain events are written to PostgreSQL `outbox_events` in the same
transaction as durable state changes. A lightweight in-process publisher
delivers pending events to WebSocket subscribers and marks them published.

Two client event types are currently emitted:

```text
order.status_changed
order.message_created
```

`order.message_created` contains message identity/sender metadata only. Chat
content is fetched through the durable HTTP message API rather than duplicated
into realtime payloads:

```text
GET  /api/v1/orders/{order_id}/messages
POST /api/v1/orders/{order_id}/messages
```

Order chat is deliberately scoped to fulfillment. Sending starts only after an
active assignment exists and is limited to active service/dispute states.
Message visibility follows the assignment participation window. Customers and
PLATFORM can read the complete order conversation; each player only sees
messages created between that assignment's acceptance and release. A
replacement player does not inherit the previous player's private conversation,
and a released player cannot see later messages or continue sending.

Realtime delivery re-checks current order participants at publish time, not only
when the socket subscribes. This prevents a player whose assignment is released
while a WebSocket is still open from receiving later order or chat events.

This remains a single-instance publisher. Production multi-instance delivery
should move the outbox consumer to a dedicated worker or Redis Streams/message
broker while PostgreSQL remains the durable source of truth.
