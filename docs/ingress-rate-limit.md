# Ingress Rate Limiting

The production Compose reference places a small Nginx guard in front of the API:

```text
TLS proxy / load balancer
        |
        v
Nginx ingress :8080
        |
        v
FastAPI :8000
```

FastAPI is no longer published directly by the production Compose stack.

## Default limits

The defaults are intentionally conservative reference values, not universal
capacity numbers:

| Surface | Rate | Burst | Purpose |
| --- | ---: | ---: | --- |
| General API | 30 req/s/IP | 60 | protect API capacity |
| Auth | 3 req/s/IP | 10 | reduce code/login/session abuse |
| Admin | 10 req/s/IP | 20 | protect privileged operations |
| WeChat payment/refund callbacks | 30 req/s/IP | 100 | absorb provider bursts without dropping normal callbacks |
| WebSocket | 5 concurrent/IP | — | bound connection fan-out |
| General HTTP connections | 20 concurrent/IP | — | basic connection pressure guard |

Rejected rate/connection requests return HTTP `429`.

The ingress also applies:

- 1 MiB maximum request body;
- request/client body timeouts;
- upstream connect/read/send timeouts;
- request ID forwarding;
- `traceparent` forwarding;
- WebSocket Upgrade/Connection handling.

## Provider callbacks

Payment and refund callbacks get a high burst allowance because provider retry
storms must not be treated like interactive login abuse. Application-side
signature verification and idempotency remain the correctness boundary.

Ingress rate limiting is only a load-shedding layer; it does not replace
provider verification.

## Client IP trust

Rate limits key on the address Nginx considers the client address.

If another reverse proxy or cloud load balancer sits in front of this ingress,
configure Nginx real-IP handling **only for the known proxy/LB CIDRs** before
using per-IP limits operationally. Never trust arbitrary public
`X-Forwarded-For` values.

## Binding

The reference stack publishes Nginx on:

```text
INGRESS_BIND_ADDRESS=127.0.0.1
INGRESS_PORT=8080
```

This is designed for a same-host TLS proxy. Change the bind address only when
network/firewall policy provides the intended protection.

## CI

The `ingress` CI job:

1. validates the Nginx configuration with `nginx -t`;
2. starts a disposable upstream and ingress container;
3. sends a parallel auth burst;
4. requires at least one request to be rejected with HTTP `429`.

This guards against accidentally removing rate limiting while editing the
production ingress config.
