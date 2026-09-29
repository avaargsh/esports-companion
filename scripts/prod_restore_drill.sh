#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <backup.dump>" >&2
  exit 64
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/deploy/compose/production.yml"
env_file="$repo_root/.env.production"
backup="$1"
drill_db="esports_restore_drill"

if [[ ! -f "$backup" ]]; then
  echo "backup not found: $backup" >&2
  exit 66
fi

if [[ -f "$backup.sha256" ]]; then
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$(dirname "$backup")" && sha256sum -c "$(basename "$backup").sha256")
  else
    expected="$(awk '{print $1}' "$backup.sha256")"
    actual="$(shasum -a 256 "$backup" | awk '{print $1}')"
    [[ "$expected" == "$actual" ]] || {
      echo "backup checksum mismatch" >&2
      exit 67
    }
  fi
fi

cleanup() {
  docker compose     --env-file "$env_file"     -f "$compose_file"     exec -T postgres sh -ec "
      export PGPASSWORD="\$(cat /run/secrets/postgres_password)"
      psql -U esports -d postgres -v ON_ERROR_STOP=1         -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$drill_db' AND pid <> pg_backend_pid();"         -c "DROP DATABASE IF EXISTS $drill_db;"
    " >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose   --env-file "$env_file"   -f "$compose_file"   exec -T postgres sh -ec "
    export PGPASSWORD="\$(cat /run/secrets/postgres_password)"
    psql -U esports -d postgres -v ON_ERROR_STOP=1       -c "DROP DATABASE IF EXISTS $drill_db;"       -c "CREATE DATABASE $drill_db OWNER esports;"
  "

cat "$backup" | docker compose   --env-file "$env_file"   -f "$compose_file"   exec -T postgres sh -ec "
    export PGPASSWORD="\$(cat /run/secrets/postgres_password)"
    exec pg_restore -U esports -d $drill_db --no-owner --no-privileges --exit-on-error
  "

docker compose   --env-file "$env_file"   -f "$compose_file"   exec -T postgres sh -ec "
    export PGPASSWORD="\$(cat /run/secrets/postgres_password)"
    psql -U esports -d $drill_db -v ON_ERROR_STOP=1 -At       -c 'SELECT version_num FROM alembic_version;'       -c 'SELECT count(*) FROM users;'       -c 'SELECT count(*) FROM games;'       -c 'SELECT count(*) FROM service_skus;'       -c 'SELECT count(*) FROM provider_offerings;'
  "

echo "prod_restore_drill_ok backup=$backup database=$drill_db"
