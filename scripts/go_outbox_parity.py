#!/usr/bin/env python3
"""Verify M5.1 Go transactional outbox publisher semantics."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from typing import Any

import psycopg
import redis

from go_claim_parity import call, dsn, expect


def stop_fastapi_reference() -> None:
    path = Path("/tmp/fastapi.pid")
    if not path.exists():
        return
    pid = int(path.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError("FastAPI reference did not stop before outbox worker test")


def start_worker(index: int) -> tuple[subprocess.Popen[bytes], Any]:
    env = os.environ.copy()
    env["OUTBOX_POLL_INTERVAL_MS"] = "25"
    env["OUTBOX_BATCH_SIZE"] = "10"
    log = open(f"/tmp/api-go-outbox-worker-{index}.log", "wb")
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


def wait_subscriptions(pubsub: Any, expected: int) -> None:
    seen = 0
    deadline = time.time() + 5
    while seen < expected and time.time() < deadline:
        message = pubsub.get_message(timeout=0.2)
        if not message:
            continue
        if message["type"] == "subscribe":
            seen += 1
    if seen != expected:
        raise AssertionError(
            f"Redis Pub/Sub subscriptions not ready: {seen}/{expected}"
        )


def insert_events(
    order_id: str,
    count: int,
) -> list[tuple[str, str, dict[str, Any]]]:
    events: list[tuple[str, str, dict[str, Any]]] = []
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            for index in range(count):
                event_id = str(uuid.uuid4())
                event_type = (
                    "ORDER_MESSAGE_CREATED"
                    if index == 0
                    else f"OUTBOX_PARITY_{index:02d}"
                )
                payload = {
                    "orderId": order_id,
                    "sequence": index,
                    "status": f"TEST_{index:02d}",
                }
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
                        'ORDER',
                        %s,
                        %s,
                        %s::json,
                        'PENDING',
                        clock_timestamp()
                    )
                    """,
                    (
                        event_id,
                        order_id,
                        event_type,
                        json.dumps(payload),
                    ),
                )
                events.append((event_id, event_type, payload))
        connection.commit()
    return events


def collect_messages(
    pubsub: Any,
    expected_ids: set[str],
    expected_channels: set[str],
) -> dict[str, set[str]]:
    seen: dict[str, set[str]] = {event_id: set() for event_id in expected_ids}
    deadline = time.time() + 20

    while time.time() < deadline:
        if all(channels == expected_channels for channels in seen.values()):
            return seen
        message = pubsub.get_message(timeout=0.2)
        if not message or message["type"] != "message":
            continue
        channel = str(message["channel"])
        try:
            payload = json.loads(message["data"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise AssertionError(f"invalid outbox Redis payload: {message!r}") from exc
        event_id = payload.get("eventId")
        if event_id not in expected_ids:
            continue
        if channel in seen[event_id]:
            raise AssertionError(
                f"duplicate outbox delivery event={event_id} channel={channel}"
            )
        if channel not in expected_channels:
            raise AssertionError(
                f"unexpected outbox channel event={event_id} channel={channel}"
            )
        seen[event_id].add(channel)

        event_type = payload.get("eventType")
        expected_type = (
            "order.message_created"
            if event_type == "ORDER_MESSAGE_CREATED"
            else "order.status_changed"
        )
        if payload.get("type") != expected_type:
            raise AssertionError(
                f"message type mismatch event={event_id} payload={payload!r}"
            )

    missing = {
        event_id: sorted(expected_channels - channels)
        for event_id, channels in seen.items()
        if channels != expected_channels
    }
    raise AssertionError(f"timed out waiting for outbox delivery: {missing!r}")


def verify_published(event_ids: list[str]) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, status, published_at IS NOT NULL
                FROM outbox_events
                WHERE id = ANY(%s::uuid[])
                ORDER BY id
                """,
                (event_ids,),
            )
            rows = cursor.fetchall()
    if len(rows) != len(event_ids):
        raise AssertionError(
            f"published row count = {len(rows)}, want {len(event_ids)}"
        )
    bad = [row for row in rows if row[1:] != ("PUBLISHED", True)]
    if bad:
        raise AssertionError(f"outbox rows not published: {bad!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    bootstrap = expect(
        call(args.python_base, "/api/v1/dev/bootstrap"),
        200,
        "bootstrap before outbox cutover",
    ).body
    customer_id = bootstrap["customerUserId"]
    customer_headers = {"X-User-Id": customer_id}
    sku_id = bootstrap["games"][0]["skus"][0]["id"]

    order = expect(
        call(
            args.go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": "go-outbox-worker-parity",
            },
        ),
        201,
        "create outbox parity order",
    ).body

    stop_fastapi_reference()

    redis_client = redis.Redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )
    redis_client.ping()
    order_channel = f"realtime:order:{order['id']}"
    user_channel = f"realtime:user:{customer_id}"
    expected_channels = {order_channel, user_channel}
    pubsub = redis_client.pubsub(ignore_subscribe_messages=False)
    pubsub.subscribe(order_channel, user_channel)
    wait_subscriptions(pubsub, 2)

    workers: list[tuple[subprocess.Popen[bytes], Any]] = []
    try:
        workers = [start_worker(1), start_worker(2)]
        for process, _log in workers:
            time.sleep(0.05)
            if process.poll() is not None:
                raise AssertionError(
                    f"outbox worker exited early with {process.returncode}"
                )

        events = insert_events(order["id"], 40)
        expected_ids = {event_id for event_id, _event_type, _payload in events}
        seen = collect_messages(pubsub, expected_ids, expected_channels)

        if len(seen) != 40:
            raise AssertionError(f"delivered events = {len(seen)}, want 40")
        verify_published(sorted(expected_ids))

        with psycopg.connect(dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM outbox_events
                    WHERE id = ANY(%s::uuid[])
                      AND status = 'PENDING'
                    """,
                    (sorted(expected_ids),),
                )
                if cursor.fetchone() != (0,):
                    raise AssertionError("outbox parity events remained PENDING")

        print(
            "PASS two Go workers claim 40 events with SKIP LOCKED, "
            "publish each event once per realtime channel, and mark PUBLISHED"
        )
    finally:
        pubsub.close()
        redis_client.close()
        for process, log in workers:
            stop_worker(process, log)

    print("M5.1 transactional outbox publisher parity PASS")
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
        redis.RedisError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"M5.1 outbox publisher parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
