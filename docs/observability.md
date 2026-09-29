# Metrics and OpenTelemetry

The API exposes Prometheus metrics on the internal FastAPI endpoint:

```text
GET /metrics
```

The production Nginx ingress intentionally returns `404` for public
`/metrics`. Scrape the API directly on the private service network.

## Prometheus metrics

Current application metrics include:

```text
esports_http_requests_total
esports_http_request_duration_seconds
esports_http_inflight_requests
esports_order_transitions_total
```

HTTP labels use the stable FastAPI route template, never a raw request path.
Unknown paths collapse to `route="unmatched"`, preventing UUID/order IDs from
creating unbounded Prometheus cardinality.

Latency uses a Histogram so p95/p99 can be calculated server-side from buckets.

Example queries:

```promql
sum(rate(esports_http_requests_total{status=~"5.."}[5m]))
/
sum(rate(esports_http_requests_total[5m]))
```

```promql
histogram_quantile(
  0.99,
  sum by (le, route) (
    rate(esports_http_request_duration_seconds_bucket[5m])
  )
)
```

## OpenTelemetry traces

Tracing is optional and disabled by default:

```text
OTEL_ENABLED=false
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=
OTEL_TRACE_SAMPLE_RATIO=0.10
OTEL_EXPORT_TIMEOUT_SECONDS=5
```

To export traces to an OTLP/HTTP Collector:

```text
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces
```

The tracer uses parent-based ratio sampling. Incoming W3C `traceparent`
context is extracted, request spans are created as server spans, and JSON logs
include `trace_id` / `span_id` when a valid trace context exists.

Resource attributes include:

```text
service.name
service.version        <- COMMIT_SHA
deployment.environment.name
```

OpenTelemetry recommends exporting telemetry through a Collector in production,
rather than coupling the application directly to a visualization/backend.

## Prometheus worker model

The reference Production Compose runs one Uvicorn worker:

```text
UVICORN_WORKERS=1
```

The Python Prometheus client registry is process-local. The reference avoids
silently returning partial metrics from one of multiple workers. Scale the
single-node reference with care; for multiple worker processes configure the
Prometheus client's multiprocess mode, or prefer multiple independently scraped
API replicas.

## Correlation

Every request continues to return `X-Request-Id`. Logs now correlate:

```text
request_id
trace_id
span_id
method
route
status_code
latency_ms
```

Request bodies, bearer tokens, WeChat login codes and payment credentials are
not logged.


## Operational backlog metrics

A read-only PostgreSQL scanner exports:

```text
esports_operational_metrics_scan_success
esports_outbox_pending
esports_outbox_oldest_pending_seconds
esports_refunds_inflight
esports_refunds_oldest_inflight_seconds
esports_withdrawals_pending
esports_withdrawals_oldest_pending_seconds
esports_disputes_open
esports_disputes_oldest_open_seconds
```

These gauges back the reference alert rules in
`deploy/observability/alerts.yml`.
