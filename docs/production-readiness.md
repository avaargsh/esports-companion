# Production Readiness

The API fails closed when `APP_ENV=production`.

## Startup validation

Production requires:

- `AUTH_PROVIDER=wechat`;
- `PAYMENT_PROVIDER=wechat`;
- a non-default session signing key of at least 32 characters;
- WeChat Mini Program and merchant credentials;
- public HTTPS payment callback URLs;
- explicit public HTTPS CORS origins.

If `REFUND_PROVIDER=wechat`, the refund callback URL is also mandatory.

Invalid production configuration prevents the application process from starting.

## Secret files

Sensitive values may be provided directly through environment variables or by
mounting secret files and setting the corresponding `*_FILE` variable.

Supported file-backed secrets:

```text
SESSION_SIGNING_KEY_FILE
WECHAT_APP_SECRET_FILE
WECHAT_MCH_PRIVATE_KEY_FILE
WECHAT_PAY_API_V3_KEY_FILE
WECHAT_PAY_PLATFORM_CERTIFICATE_FILE
```

File-backed values override the inline value. This keeps the application
compatible with Docker/Kubernetes secret mounts without coupling the domain to a
specific secret manager.

## Health probes

```text
GET /livez   process liveness; does not contact dependencies
GET /readyz  PostgreSQL + Redis readiness
GET /health  compatibility alias with detailed dependency state
```

`READINESS_REQUIRE_REDIS=false` may be used only when operators deliberately
accept degraded Redis-dependent features. PostgreSQL is always required.

## Request observability

Every HTTP response includes `X-Request-Id`. Structured JSON request logs
include:

- request id;
- method and path;
- HTTP status;
- latency in milliseconds;
- service, environment and commit SHA;
- incoming W3C `traceparent` when present.

No request body, token, WeChat code, secret, or payment credential is logged.

## Production surface

`/api/v1/dev/*` routes are not registered in production. Legacy identity
headers remain unavailable through the existing production auth guard.

Set `EXPOSE_API_DOCS=false` in production to remove Swagger/ReDoc/OpenAPI
routes from the public API surface.
