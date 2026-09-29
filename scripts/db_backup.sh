#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: DATABASE_URL=... $0 <output.dump>" >&2
  exit 64
fi

: "${DATABASE_URL:?DATABASE_URL is required}"

output="$1"
dsn="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
mkdir -p "$(dirname "$output")"

pg_dump   --dbname="$dsn"   --format=custom   --compress=6   --no-owner   --no-privileges   --file="$output"

pg_restore --list "$output" >/dev/null

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$output" > "$output.sha256"
else
  shasum -a 256 "$output" > "$output.sha256"
fi

bytes="$(wc -c < "$output" | tr -d ' ')"
echo "backup_ok path=$output bytes=$bytes checksum=$output.sha256"
