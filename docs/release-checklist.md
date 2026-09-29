# Release Checklist

Use this before exposing a production deployment to real users or money.

## Configuration and secrets

- [ ] `APP_ENV=production`.
- [ ] `AUTH_PROVIDER=wechat` and `PAYMENT_PROVIDER=wechat`.
- [ ] Refund policy chosen explicitly; use `REFUND_PROVIDER=wechat` for automated refunds.
- [ ] Session signing key is random and stored outside Git.
- [ ] AppSecret, merchant private key, APIv3 key and platform certificate are mounted from secrets.
- [ ] No real secret is present in `.env.production`, source control, image layers or CI logs.
- [ ] `EXPOSE_API_DOCS=false` unless intentionally exposed.

## Network and WeChat

- [ ] Public API is HTTPS only.
- [ ] CORS contains only expected HTTPS admin origins.
- [ ] Mini Program request/socket domains are configured in WeChat.
- [ ] Payment and refund callback URLs are public HTTPS endpoints.
- [ ] Reverse proxy forwards the original request body unchanged to callback endpoints.
- [ ] Ingress applies request-size limits and rate limits, especially auth/payment/admin endpoints.

## Data and money

- [ ] Alembic migration tested against a copy of production-like data.
- [ ] PostgreSQL backup policy enabled.
- [ ] A restore drill has been completed and timed.
- [ ] Redis loss has been tested; durable order/money state remains reconstructable.
- [ ] Payment callback idempotency tested.
- [ ] Refund callback + query reconciliation tested.
- [ ] Settlement and withdrawal reconciliation ownership is assigned to an operator.

## Runtime and observability

- [ ] `/livez` and `/readyz` wired into the runtime/load balancer.
- [ ] Structured API logs are collected centrally.
- [ ] `COMMIT_SHA` is populated for each release.
- [ ] Alerts exist for API 5xx, readiness failures, callback failures, stuck outbox events, stuck refunds and database capacity.
- [ ] Time synchronization is healthy; WeChat signature verification depends on timestamp windows.

## Acceptance

- [ ] CI API, HTTP Smoke, MiniApp, Admin and API Image jobs are green.
- [ ] `make smoke` passes in the staging/demo environment.
- [ ] WeChat login works with a real Mini Program account in staging.
- [ ] A low-value real payment and real refund have been exercised end to end.
- [ ] User, player and platform role revocation has been verified.

## Deployment

- [ ] Database migration ownership is single-writer for multi-replica deployments.
- [ ] Rollback procedure is documented for application code.
- [ ] Schema changes used in the release are backward-compatible with the chosen rollback window.
- [ ] On-call/operator contact and incident procedure are known.

The single-node Compose configuration is a reference deployment, not a substitute
for an external security review, load test, backup strategy or operational SLO.
