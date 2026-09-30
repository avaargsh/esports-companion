# Prometheus scrape reference

This directory contains the private-service scrape configuration for the API.

```text
Prometheus -> http://api:8000/metrics
```

Do not scrape through the public Nginx ingress; it intentionally returns
`404` for `/metrics`.

The default interval is 15 seconds. Adjust retention, remote-write, external
labels and HA topology in the deployment that owns Prometheus.

## Go worker metrics during cutover

The Go background runtime exposes an internal-only Prometheus surface on
`WORKER_METRICS_ADDR` (default `:9091`):

```text
Prometheus -> http://worker-go:9091/metrics
```

Add that private target when M5 workers are deployed. Do not proxy the worker
metrics port through public ingress. The durable backlog gauges keep the same
`esports_*` names as the FastAPI reference; Go additionally exports
`esports_worker_*` cycle health.
