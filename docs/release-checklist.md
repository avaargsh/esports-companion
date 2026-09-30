# Release Checklist

Use this before exposing a production deployment to real users or money.

## Product gate and change freeze

- [ ] The automated **Release Checklist Gate** is green. It requires API, Mini Program, Admin, API image, HTTP product slice, backup/restore, ingress, metrics and staging configuration jobs to pass.
- [ ] The HTTP product slice proves: login -> order -> payment -> public claim -> start -> finish -> customer confirm -> review.
- [ ] Admin acceptance proves the dispute queue can resolve a real order path and the withdrawal queue can list, approve and reject requests.
- [ ] Discovery acceptance proves only approved/available players with active Offerings are returned, and designated booking bypasses the public order pool.
- [ ] **Change freeze:** do not add a new auth evidence, authority envelope or authority admission variant until a low-value real withdrawal has been completed from the Mini Program request through Admin review and external payout reconciliation.


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
- [ ] `ingress` CI is green and Nginx request-size/rate/connection limits have been reviewed for expected traffic.
- [ ] If a TLS proxy/LB sits in front, Nginx real-IP trust is restricted to known proxy/LB CIDRs.

## Data and money

- [ ] Alembic migration tested against a copy of production-like data.
- [ ] PostgreSQL backup policy enabled and backup artifacts are stored off-host.
- [ ] `backup-restore` CI is green.
- [ ] `make prod-restore-drill BACKUP=...` has been completed against the release backup and timed.
- [ ] Redis loss has been tested; durable order/money state remains reconstructable.
- [ ] Payment callback idempotency tested.
- [ ] Refund callback + query reconciliation tested.
- [ ] Settlement and withdrawal reconciliation ownership is assigned to an operator.

## Runtime and observability

- [ ] `/livez` and `/readyz` wired into the runtime/load balancer.
- [ ] Structured API logs are collected centrally.
- [ ] `/metrics` is scraped only from the private service network and is not public through ingress.
- [ ] OTLP trace export is configured to an approved Collector/backend, or tracing is explicitly disabled by operational decision.
- [ ] `COMMIT_SHA` is populated for each release.
- [ ] `promtool` validation is green for Prometheus config and alert rules.
- [ ] Alertmanager/notification routing is connected for API down, 5xx, latency, stuck outbox/refund/withdrawal and dispute aging alerts.
- [ ] Reference alert thresholds have been reviewed against the actual traffic profile and business SLA.
- [ ] Time synchronization is healthy; WeChat signature verification depends on timestamp windows.

## Acceptance

- [ ] CI API, HTTP Smoke, MiniApp, Admin and API Image jobs are green.
- [ ] `make smoke` passes in the staging/demo environment.
- [ ] `make staging-preflight` passes with dedicated staging secrets.
- [ ] `make staging-check BASE_URL=...` proves dev routes and public metrics are closed.
- [ ] WeChat login works with a real Mini Program account in staging.
- [ ] A low-value real payment and real refund have been exercised end to end.
- [ ] User, player and platform role revocation has been verified.
- [ ] Mini Program release build uses `VITE_AUTH_MODE=wechat` and the intended HTTPS API origin.
- [ ] Admin release build uses `VITE_ADMIN_AUTH_MODE=bearer`; no operator token is embedded in the build.
- [ ] A PLATFORM operator session can load the operations SLA queue, disputes, refunds, withdrawals and settlements.
- [ ] FINISH_REQUESTED aging appears in both Prometheus metrics/alerts and the Admin operations queue.
- [ ] A low-value real withdrawal has been requested, frozen, externally paid, approved with the same payout reference, and `make staging-withdrawal-acceptance WITHDRAWAL_ID=... PAYOUT_REF=...` returns `PASS` (see [Real Withdrawal Acceptance](real-withdrawal-acceptance.md)).
- [ ] Discovery shows only approved/available players with active Offerings, and designated booking bypasses the public order pool.

## Deployment

- [ ] Database migration ownership is single-writer for multi-replica deployments.
- [ ] Rollback procedure is documented for application code.
- [ ] Schema changes used in the release are backward-compatible with the chosen rollback window.
- [ ] On-call/operator contact and incident procedure are known.

The single-node Compose configuration is a reference deployment, not a substitute
for an external security review, load test, backup strategy or operational SLO.
