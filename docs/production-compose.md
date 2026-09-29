# Production Compose

The repository keeps development and production deployment modes separate.

- `docker-compose.yml`: local demo, hot reload and demo seed.
- `deploy/compose/production.yml`: hardened single-node production reference.

The production stack:

- builds the API without development/test dependencies;
- runs the API as UID/GID `10001:10001`;
- never enables Uvicorn reload;
- runs Alembic migrations but never seeds demo identities;
- keeps PostgreSQL and Redis off host ports;
- does not publish FastAPI directly; Nginx ingress is the only published application service;
- binds ingress to `127.0.0.1:8080` by default;
- mounts sensitive application values through Docker secrets;
- uses a read-only API root filesystem and drops Linux capabilities;
- uses `/readyz` for container health.

## Prepare

```bash
cp .env.production.example .env.production
mkdir -p deploy/secrets
```

Populate the files documented in `deploy/secrets/README.md`. Then edit only
the non-secret identifiers, callback URLs, public admin origin, and release SHA
in `.env.production`.

## Start

```bash
make prod-up
make prod-logs
```

The reference Compose file does not terminate TLS. Put Caddy, Nginx, Traefik,
a cloud load balancer, or Kubernetes ingress in front of
`127.0.0.1:8080` and expose only HTTPS publicly. The embedded Nginx layer adds request/connection rate limiting before traffic reaches FastAPI.

## Stop

```bash
make prod-down
```

## Multi-node note

The single-node reference runs `alembic upgrade head` before the API starts.
For multiple API replicas, move migrations to a single deployment job rather
than allowing every replica to run migrations concurrently.


See [Ingress Rate Limiting](ingress-rate-limit.md) for the reference limits and trusted-proxy considerations.
