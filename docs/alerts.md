# Alert Rules

Reference Prometheus alert rules live in:

```text
deploy/observability/alerts.yml
```

The rules deliberately combine request symptoms with durable business backlog
signals.

## Platform alerts

- API target down.
- 5xx ratio above 5% with a minimum traffic floor.
- p99 request latency above 1.5 seconds.
- operational PostgreSQL metrics scan failure.

## Transaction alerts

- transactional outbox oldest pending event > 60 seconds;
- in-flight refund oldest age > 15 minutes;
- pending withdrawal oldest age > 1 hour;
- unresolved dispute oldest age > 24 hours.

Thresholds are reference defaults. They should be tuned from observed
production traffic and the actual service/support SLA.

The operational gauges are refreshed by a read-only background task every 15
seconds by default:

```text
OPERATIONAL_METRICS_SCAN_SECONDS=15
```

The worker never changes business state. PostgreSQL remains the source of truth;
Prometheus is only an observation surface.

Both the Prometheus configuration and alert rules are validated in CI with
`promtool`.

See [Alert Runbook](alert-runbook.md) for response steps.
