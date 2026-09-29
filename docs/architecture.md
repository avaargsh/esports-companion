# Architecture

v0.1 uses a **Modular Monolith + Redis**.

```text
WeChat Mini Program -> FastAPI -> PostgreSQL
                         |
                         +-> Redis
```

PostgreSQL is the source of truth. Redis is reconstructable acceleration state for order pool, claim lock, presence and cache. No microservice split before the Golden Slice proves a real boundary.
