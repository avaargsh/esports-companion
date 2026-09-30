#!/usr/bin/env python3
"""Verify M5.5 Go worker operational metrics against PostgreSQL truth."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid
import urllib.request
from typing import Any

import psycopg
from prometheus_client.parser import text_string_to_metric_families

from go_claim_parity import call, dsn, expect


def metric_samples(base: str) -> list[Any]:
    with urllib.request.urlopen(base.rstrip("/") + "/metrics", timeout=3) as response:
        text = response.read().decode("utf-8")
    samples: list[Any] = []
    for family in text_string_to_metric_families(text):
        samples.extend(family.samples)
    return samples


def metric_value(
    samples: list[Any],
    name: str,
    labels: dict[str, str] | None = None,
) -> float:
    labels = labels or {}
    for sample in samples:
        if sample.name != name:
            continue
        if all(sample.labels.get(key) == value for key, value in labels.items()):
            return float(sample.value)
    raise AssertionError(f"metric missing: {name} labels={labels!r}")


def wait_metrics(base: str, timeout: float = 10.0) -> list[Any]:
    """Wait until mutation workers finish first cycle and scanner runs after them."""
    deadline = time.time() + timeout
    last_error: Exception | None = None
    first_operational_success: float | None = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base.rstrip("/") + "/livez", timeout=1) as response:
                if response.status != 200:
                    raise AssertionError(f"worker livez={response.status}")
            samples = metric_samples(base)
            if metric_value(
                samples,
                "esports_operational_metrics_scan_success",
            ) != 1:
                time.sleep(0.1)
                continue

            outbox_success = metric_value(
                samples,
                "esports_worker_last_success_unixtime",
                {"worker": "outbox"},
            )
            timeout_success = metric_value(
                samples,
                "esports_worker_last_success_unixtime",
                {"worker": "order-timeout"},
            )
            operational_success = metric_value(
                samples,
                "esports_worker_last_success_unixtime",
                {"worker": "operational-metrics"},
            )
            if outbox_success <= 0 or timeout_success <= 0 or operational_success <= 0:
                time.sleep(0.1)
                continue

            if first_operational_success is None:
                first_operational_success = operational_success
                time.sleep(0.1)
                continue

            # The business workers now sleep for ten minutes. Require one fresh
            # PostgreSQL metrics scan after that quiescent point so the baseline
            # cannot include rows that the first outbox/timeout cycle is removing.
            if operational_success > first_operational_success:
                return samples
        except (OSError, AssertionError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise AssertionError(f"worker metrics did not become quiescent: {last_error!r}")


def start_worker(metrics_addr: str) -> tuple[subprocess.Popen[bytes], Any]:
    env = os.environ.copy()
    env.update(
        {
            "WORKER_METRICS_ADDR": metrics_addr,
            "OPERATIONAL_METRICS_SCAN_SECONDS": "1",
            # Business workers run one initial cycle before fixtures are inserted,
            # then stay inert while the metrics scanner observes the fixtures.
            "OUTBOX_POLL_INTERVAL_MS": "600000",
            "ORDER_TIMEOUT_SCAN_SECONDS": "600",
            "REFUND_RECONCILE_SCAN_SECONDS": "600",
            "REFUND_PROVIDER": "manual",
        }
    )
    log = open("/tmp/api-go-operational-metrics-worker.log", "wb")
    process = subprocess.Popen(
        ["/tmp/esports-worker-go"],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return process, log


def stop_worker(process: subprocess.Popen[bytes], log: Any) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log.close()


def seed_ids() -> tuple[str, str]:
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
                FROM service_skus
                WHERE status = 'ACTIVE'
                ORDER BY created_at, id
                LIMIT 1
                """
            )
            sku = cursor.fetchone()
    if customer is None or sku is None:
        raise AssertionError("metrics parity seed identities/catalog missing")
    return customer[0], sku[0]


def create_order(
    go_base: str,
    customer_id: str,
    sku_id: str,
    label: str,
) -> dict[str, Any]:
    return expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers={"X-User-Id": customer_id},
            body={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": label,
            },
        ),
        201,
        label,
    ).body


def insert_operational_fixtures(
    go_base: str,
    customer_id: str,
    sku_id: str,
) -> None:
    finish = create_order(
        go_base,
        customer_id,
        sku_id,
        "worker-metrics-finish-overdue",
    )
    assignment = create_order(
        go_base,
        customer_id,
        sku_id,
        "worker-metrics-assignment-overdue",
    )

    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orders
                SET status = 'FINISH_REQUESTED',
                    finish_requested_at = clock_timestamp() - interval '2 hours',
                    updated_at = clock_timestamp()
                WHERE id = %s::uuid
                """,
                (finish["id"],),
            )
            cursor.execute(
                """
                UPDATE orders
                SET status = 'ACCEPTED',
                    accepted_at = clock_timestamp() - interval '2 hours',
                    updated_at = clock_timestamp()
                WHERE id = %s::uuid
                """,
                (assignment["id"],),
            )
            cursor.execute(
                """
                INSERT INTO outbox_events (
                    id,
                    aggregate_type,
                    aggregate_id,
                    event_type,
                    payload_json,
                    status,
                    created_at
                )
                VALUES (
                    %s::uuid,
                    'TEST',
                    %s,
                    'WORKER_METRICS_FIXTURE',
                    '{}'::json,
                    'PENDING',
                    clock_timestamp() - interval '2 minutes'
                )
                """,
                (str(uuid.uuid4()), f"metrics-{uuid.uuid4().hex}"),
            )
        connection.commit()


def wait_for_delta(
    base: str,
    baseline: dict[str, float],
    timeout: float = 8.0,
) -> list[Any]:
    deadline = time.time() + timeout
    last: list[Any] = []
    while time.time() < deadline:
        last = metric_samples(base)
        try:
            if (
                metric_value(last, "esports_outbox_pending")
                >= baseline["outbox"] + 3
                and metric_value(last, "esports_finish_requests_pending")
                >= baseline["finish"] + 1
                and metric_value(last, "esports_finish_requests_overdue")
                >= baseline["finish_overdue"] + 1
                and metric_value(last, "esports_assignments_start_overdue")
                >= baseline["assignment_overdue"] + 1
            ):
                return last
        except AssertionError:
            pass
        time.sleep(0.15)

    observed = {
        "outbox": metric_value(last, "esports_outbox_pending"),
        "finish": metric_value(last, "esports_finish_requests_pending"),
        "finish_overdue": metric_value(last, "esports_finish_requests_overdue"),
        "assignment_overdue": metric_value(
            last,
            "esports_assignments_start_overdue",
        ),
    }
    raise AssertionError(
        "operational metrics did not reflect PostgreSQL fixtures: "
        f"baseline={baseline!r} observed={observed!r}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    parser.add_argument("--metrics-base", default="http://127.0.0.1:19091")
    args = parser.parse_args()

    customer_id, sku_id = seed_ids()
    metrics_addr = args.metrics_base.removeprefix("http://")
    worker, log = start_worker(metrics_addr)
    try:
        initial = wait_metrics(args.metrics_base)
        baseline = {
            "outbox": metric_value(initial, "esports_outbox_pending"),
            "finish": metric_value(initial, "esports_finish_requests_pending"),
            "finish_overdue": metric_value(
                initial,
                "esports_finish_requests_overdue",
            ),
            "assignment_overdue": metric_value(
                initial,
                "esports_assignments_start_overdue",
            ),
        }

        insert_operational_fixtures(
            args.go_base,
            customer_id,
            sku_id,
        )
        samples = wait_for_delta(args.metrics_base, baseline)

        if metric_value(
            samples,
            "esports_outbox_oldest_pending_seconds",
        ) < 120:
            raise AssertionError("outbox oldest age did not reflect fixture")
        if metric_value(
            samples,
            "esports_finish_requests_oldest_seconds",
        ) < 3600:
            raise AssertionError("finish oldest age did not reflect fixture")
        if metric_value(
            samples,
            "esports_operational_metrics_scan_success",
        ) != 1:
            raise AssertionError("operational scan success gauge is not healthy")

        for worker_name in ("outbox", "order-timeout", "operational-metrics"):
            total_cycles = sum(
                metric_value(
                    samples,
                    "esports_worker_cycles_total",
                    {"worker": worker_name, "result": result},
                )
                if any(
                    sample.name == "esports_worker_cycles_total"
                    and sample.labels.get("worker") == worker_name
                    and sample.labels.get("result") == result
                    for sample in samples
                )
                else 0
                for result in ("success", "partial", "failure")
            )
            if total_cycles < 1:
                raise AssertionError(f"worker cycle missing for {worker_name}")
            if metric_value(
                samples,
                "esports_worker_last_success_unixtime",
                {"worker": worker_name},
            ) <= 0:
                raise AssertionError(f"worker last success missing for {worker_name}")

        for name in (
            "esports_refunds_inflight",
            "esports_refunds_oldest_inflight_seconds",
            "esports_refunds_reconcile_due",
            "esports_withdrawals_pending",
            "esports_withdrawals_oldest_pending_seconds",
            "esports_disputes_open",
            "esports_disputes_oldest_open_seconds",
        ):
            metric_value(samples, name)

        print(
            "PASS worker metrics expose PostgreSQL backlog/age gauges "
            "and worker-cycle health"
        )
    finally:
        stop_worker(worker, log)

    print("M5.5 operational worker metrics parity PASS")
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
        subprocess.SubprocessError,
    ) as exc:
        print(f"M5.5 worker metrics parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
