#!/usr/bin/env python3
import json
import os
import sys

import psycopg


def normalize(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 64

    required_tables = {
        "alembic_version",
        "users",
        "games",
        "service_skus",
        "player_profiles",
        "provider_offerings",
        "orders",
        "order_events",
        "payment_transactions",
        "settlements",
        "ledger_entries",
        "disputes",
        "refunds",
    }

    with psycopg.connect(normalize(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                """
            )
            tables = {row[0] for row in cur.fetchall()}
            missing = sorted(required_tables - tables)
            if missing:
                raise RuntimeError(f"missing tables: {','.join(missing)}")

            cur.execute("select version_num from alembic_version")
            versions = [row[0] for row in cur.fetchall()]
            if len(versions) != 1:
                raise RuntimeError(f"unexpected alembic heads: {versions}")

            counts = {}
            for table in (
                "users",
                "games",
                "service_skus",
                "player_profiles",
                "provider_offerings",
            ):
                cur.execute(f'SELECT count(*) FROM "{table}"')
                counts[table] = cur.fetchone()[0]

            if min(counts.values()) <= 0:
                raise RuntimeError(f"seed/core data missing: {counts}")

    print(
        json.dumps(
            {
                "status": "PASS",
                "alembicVersion": versions[0],
                "counts": counts,
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
