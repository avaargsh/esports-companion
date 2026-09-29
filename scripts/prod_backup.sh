#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/deploy/compose/production.yml"
env_file="$repo_root/.env.production"
backup_dir="${BACKUP_DIR:-$repo_root/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${1:-$backup_dir/esports-$timestamp.dump}"

mkdir -p "$(dirname "$output")"

docker compose   --env-file "$env_file"   -f "$compose_file"   exec -T postgres sh -ec '
    export PGPASSWORD="$(cat /run/secrets/postgres_password)"
    exec pg_dump -U esports -d esports -Fc --compress=6 --no-owner --no-privileges
  ' > "$output"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$output" > "$output.sha256"
else
  shasum -a 256 "$output" > "$output.sha256"
fi

bytes="$(wc -c < "$output" | tr -d ' ')"
echo "prod_backup_ok path=$output bytes=$bytes checksum=$output.sha256"
