#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: TARGET_DATABASE_URL=... RESTORE_CONFIRM=RESTORE_TO_TARGET $0 <backup.dump>" >&2
  exit 64
fi

: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL is required}"
: "${RESTORE_CONFIRM:?RESTORE_CONFIRM is required}"

if [[ "$RESTORE_CONFIRM" != "RESTORE_TO_TARGET" ]]; then
  echo "refusing restore: set RESTORE_CONFIRM=RESTORE_TO_TARGET" >&2
  exit 65
fi

backup="$1"
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

target="${TARGET_DATABASE_URL/postgresql+psycopg:/postgresql:}"

pg_restore   --dbname="$target"   --no-owner   --no-privileges   --exit-on-error   "$backup"

echo "restore_ok target=$target backup=$backup"
