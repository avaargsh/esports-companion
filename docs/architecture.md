# Architecture

The product remains a **Modular Monolith + Redis**.

During the Go migration there are two implementations, but still only one
backend architecture and one durable data model:

```text
WeChat Mini Program / Admin
            |
          /api/v1
            |
      compatibility boundary
        /          \
 FastAPI            Go API
 reference           target
        \          /
         PostgreSQL
        durable truth
             |
           Redis
   reconstructable acceleration
```

PostgreSQL is the source of truth. Redis is reconstructable acceleration state
for order pool, presence, realtime delivery and cache. No microservice split
before profiling proves a real operational boundary.

The Go target uses a vertical modular-monolith layout:

```text
transport -> application service -> domain -> repository / provider ports
```

Shared runtime concerns stay under `internal/platform`; external systems stay
behind `internal/ports`. Business modules do not depend directly on WeChat,
Redis clients or HTTP framework details.

See [Go backend migration](go-backend-migration.md).
