#!/usr/bin/env bash
set -euo pipefail

network="esports-ingress-ci"
api_container="esports-ingress-api"
nginx_container="esports-ingress-nginx"

cleanup() {
  docker rm -f "$nginx_container" "$api_container" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$network" >/dev/null

docker run -d   --name "$api_container"   --network "$network"   --network-alias api   python:3.12-alpine   sh -c 'python -m http.server 8000 --bind 0.0.0.0' >/dev/null

docker run --rm   --network "$network"   --add-host api:127.0.0.1   -v "$PWD/deploy/nginx/nginx.conf:/etc/nginx/nginx.conf:ro"   -v "$PWD/deploy/nginx/proxy_params_esports:/etc/nginx/proxy_params_esports:ro"   nginx:1.27-alpine nginx -t

docker run -d   --name "$nginx_container"   --network "$network"   -p 18080:8080   -v "$PWD/deploy/nginx/nginx.conf:/etc/nginx/nginx.conf:ro"   -v "$PWD/deploy/nginx/proxy_params_esports:/etc/nginx/proxy_params_esports:ro"   nginx:1.27-alpine >/dev/null

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/ >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

code="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/livez)"
if [[ "$code" != "404" && "$code" != "200" ]]; then
  echo "ingress proxy check failed with HTTP $code" >&2
  exit 1
fi

tmp="$(mktemp)"
seq 1 40 | xargs -I{} -P40 sh -c   "curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18080/api/v1/auth/test || true"   > "$tmp"

limited="$(grep -c '^429$' "$tmp" || true)"
if [[ "$limited" -lt 1 ]]; then
  echo "expected auth rate limiting to return at least one HTTP 429" >&2
  cat "$tmp" >&2
  exit 1
fi

echo "ingress_test_ok limited_requests=$limited"
