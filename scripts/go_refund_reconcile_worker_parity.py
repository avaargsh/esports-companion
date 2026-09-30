#!/usr/bin/env python3
"""Verify M5.4 refund reconciliation scheduler with two Go workers."""

from __future__ import annotations

import argparse
import collections
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import psycopg

from go_claim_parity import call, dsn, expect
from go_refund_recovery_parity import (
    FakeRefundQueryServer,
    seed_wechat_refund,
    verify_complete,
)
from go_refund_submit_parity import create_order, refund_row


def wait_completed(refund_ids: list[str], timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    pending = set(refund_ids)
    while time.time() < deadline:
        with psycopg.connect(dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id::text, status
                    FROM refunds
                    WHERE id = ANY(%s::uuid[])
                    """,
                    (list(pending),),
                )
                for refund_id, status in cursor.fetchall():
                    if status == "COMPLETED":
                        pending.discard(refund_id)
        if not pending:
            return
        time.sleep(0.2)
    raise AssertionError(f"refunds did not complete: {sorted(pending)!r}")


def age_refunds(refund_ids: list[str], seconds: int) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE refunds
                SET updated_at = clock_timestamp() - make_interval(secs => %s)
                WHERE id = ANY(%s::uuid[])
                """,
                (seconds, refund_ids),
            )
        connection.commit()


def event_counts(refund_ids: list[str]) -> dict[str, tuple[int, int]]:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    r.id::text,
                    count(DISTINCT oe.id),
                    count(DISTINCT ob.id)
                FROM refunds r
                LEFT JOIN order_events oe
                  ON oe.order_id = r.order_id
                 AND oe.event_type = 'REFUND_COMPLETED'
                LEFT JOIN outbox_events ob
                  ON ob.aggregate_type = 'ORDER'
                 AND ob.aggregate_id = r.order_id::text
                 AND ob.event_type = 'REFUND_COMPLETED'
                WHERE r.id = ANY(%s::uuid[])
                GROUP BY r.id
                """,
                (refund_ids,),
            )
            return {
                row[0]: (int(row[1]), int(row[2]))
                for row in cursor.fetchall()
            }


def start_worker(
    base_url: str,
    name: str,
) -> tuple[subprocess.Popen[bytes], Any]:
    env = os.environ.copy()
    env.update(
        {
            "REFUND_PROVIDER": "wechat",
            "WECHAT_PAY_API_BASE_URL": base_url,
            "REFUND_RECONCILE_SCAN_SECONDS": "1",
            "REFUND_RECONCILE_MIN_AGE_SECONDS": "5",
            "REFUND_RECONCILE_BATCH_SIZE": "50",
            # Keep unrelated background scanners inert for this acceptance.
            "FINISH_CONFIRM_TIMEOUT_SECONDS": "315360000",
            "ASSIGNMENT_START_TIMEOUT_SECONDS": "315360000",
            "ORDER_TIMEOUT_SCAN_SECONDS": "3600",
            "OUTBOX_POLL_INTERVAL_MS": "60000",
            "WORKER_METRICS_ADDR": f"127.0.0.1:{19300 + int(name)}",
        }
    )
    log = open(f"/tmp/api-go-refund-worker-{name}.log", "wb")
    process = subprocess.Popen(
        ["/tmp/esports-worker-go"],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return process, log


def stop_workers(workers: list[tuple[subprocess.Popen[bytes], Any]]) -> None:
    for process, _log in workers:
        process.terminate()
    for process, log in workers:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    # M5.3 intentionally stops the FastAPI reference before this step.
    # This background-worker acceptance therefore discovers stable seed
    # identities directly from the shared PostgreSQL truth.
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id::text
                FROM users u
                LEFT JOIN player_profiles p ON p.user_id = u.id
                WHERE u.role = 'USER'
                  AND u.status = 'ACTIVE'
                  AND p.id IS NULL
                ORDER BY u.created_at, u.id
                LIMIT 1
                """
            )
            customer = cursor.fetchone()
            cursor.execute(
                """
                SELECT id::text
                FROM users
                WHERE role = 'PLATFORM'
                  AND status = 'ACTIVE'
                ORDER BY created_at, id
                LIMIT 1
                """
            )
            admin = cursor.fetchone()
            cursor.execute(
                """
                SELECT id::text
                FROM service_skus
                WHERE status = 'ACTIVE'
                ORDER BY created_at, id
                LIMIT 1
                """
            )
            sku = cursor.fetchone()
    if customer is None or admin is None or sku is None:
        raise AssertionError("required seed identities/catalog are missing")
    customer_id = customer[0]
    admin_id = admin[0]
    customer_headers = {"X-User-Id": customer_id}
    sku_id = sku[0]

    due: list[tuple[dict[str, Any], str, str]] = []
    for index in range(12):
        order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            f"refund-worker-due-{index}",
        )
        status = "SUBMITTING" if index % 2 == 0 else "PROCESSING"
        refund_id, out_refund_no, _payment_txn = seed_wechat_refund(
            order,
            customer_id=customer_id,
            admin_id=admin_id,
            status=status,
        )
        due.append((order, refund_id, out_refund_no))

    fresh: list[tuple[dict[str, Any], str, str]] = []
    for index in range(2):
        order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            f"refund-worker-fresh-{index}",
        )
        refund_id, out_refund_no, _payment_txn = seed_wechat_refund(
            order,
            customer_id=customer_id,
            admin_id=admin_id,
            status="PROCESSING",
        )
        fresh.append((order, refund_id, out_refund_no))

    due_ids = [item[1] for item in due]
    age_refunds(due_ids, 60)

    query_server = FakeRefundQueryServer()
    counts: collections.Counter[str] = collections.Counter()
    original_payload = query_server.payload

    def delayed_counted_payload(out_refund_no: str) -> dict[str, Any]:
        counts[out_refund_no] += 1
        # Hold the provider call open long enough for the second worker to see
        # the same stale candidate list. The advisory lock must prevent a
        # duplicate external query.
        time.sleep(0.15)
        return original_payload(out_refund_no)

    query_server.payload = delayed_counted_payload  # type: ignore[method-assign]
    query_server.start()

    workers = [
        start_worker(query_server.base_url, "1"),
        start_worker(query_server.base_url, "2"),
    ]
    try:
        wait_completed(due_ids)
    finally:
        stop_workers(workers)
        query_server.close()

    for order, refund_id, out_refund_no in due:
        expected_provider_id = "wx-query-" + out_refund_no[-16:]
        verify_complete(
            refund_id,
            provider_refund_id=expected_provider_id,
            evidence_key="query",
        )
        if counts[out_refund_no] != 1:
            raise AssertionError(
                f"provider query count for {refund_id} = "
                f"{counts[out_refund_no]}, expected 1"
            )

    counts_by_refund = event_counts(due_ids)
    for refund_id in due_ids:
        if counts_by_refund.get(refund_id) != (1, 1):
            raise AssertionError(
                f"refund evidence count {refund_id}="
                f"{counts_by_refund.get(refund_id)!r}"
            )
    print("PASS two Go workers reconcile due refunds exactly once")

    for _order, refund_id, out_refund_no in fresh:
        row = refund_row(refund_id)
        if row["status"] != "PROCESSING":
            raise AssertionError(f"fresh refund was reconciled early: {row!r}")
        if counts[out_refund_no] != 0:
            raise AssertionError(
                f"fresh refund reached provider query: {out_refund_no}"
            )
    print("PASS refund reconcile min-age gate preserves fresh refunds")

    print("M5.4 refund reconciliation worker parity PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AssertionError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        psycopg.Error,
    ) as exc:
        print(
            f"M5.4 refund reconciliation worker parity FAIL: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
