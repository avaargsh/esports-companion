# Security Policy

## Supported version

The current v0.1 branch is an engineering starter and reference implementation.

## Reporting a vulnerability

Please avoid publishing exploitable security details in a public issue before a fix is available. Use GitHub's private vulnerability reporting feature when enabled for the repository.

## Important v0.1 boundaries

The default development configuration is **not production authentication**:

- `X-User-Id` and `X-Admin-Id` are development/demo identity mechanisms.
- `/api/v1/dev/*` endpoints must remain unavailable in production.
- `mock-pay` is only a development payment provider.
- real WeChat login/payment must verify server-side credentials and callbacks.
- secrets must be provided through environment/secret management, never committed.

Before internet-facing production deployment, add production auth, rate limiting, secret management, TLS, structured audit retention, dependency scanning and an explicit operational backup/recovery policy.
