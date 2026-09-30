#!/usr/bin/env python3
"""Verify M5.3 Go order timeout worker semantics and multi-worker safety."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
import redis

from go_claim_parity import Response, call, dsn, expect


@dataclass(frozen=True)
class Seed:
    customer_id: str
    sku_id: str
    provider_user_id: str
    provider_player_id: str
    platform_user_id: str


def seed_context() -> Seed:
    suffix = uuid.uuid4().hex[:8]
    provider_user_id = str(uuid.uuid4())
    provider_player_id = str(uuid.uuid4())
    offering_id = str(uuid.uuid4())

    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text
                FROM users
                WHERE nickname = 'Demo Customer'
                ORDER BY created_at, id
                LIMIT 1
                """
            )
            customer = cursor.fetchone()
            if customer is None:
                raise AssertionError("seeded Demo Customer missing")

            cursor.execute(
                """
                SELECT id::text
                FROM users
                WHERE role = 'PLATFORM'
                ORDER BY created_at, id
                LIMIT 1
                """
            )
            platform = cursor.fetchone()
            if platform is None:
                raise AssertionError("platform user missing")

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
            if sku is None:
                raise AssertionError("active sku missing")

            cursor.execute(
                """
                INSERT INTO users (
                    id, nickname, role, status, created_at, updated_at
                )
                VALUES (
                    %s::uuid, %s, 'USER', 'ACTIVE',
                    clock_timestamp(), clock_timestamp()
                )
                """,
                (provider_user_id, f"timeout-provider-{suffix}"),
            )
            cursor.execute(
                """
                INSERT INTO player_profiles (
                    id, user_id, display_name, bio,
                    verification_status, service_status,
                    rating, order_count, created_at, updated_at
                )
                VALUES (
                    %s::uuid, %s::uuid, %s, '',
                    'APPROVED', 'AVAILABLE',
                    0, 0, clock_timestamp(), clock_timestamp()
                )
                """,
                (
                    provider_player_id,
                    provider_user_id,
                    f"Timeout Provider {suffix}",
                ),
            )
            cursor.execute(
                """
                INSERT INTO provider_offerings (
                    id, player_id, sku_id, description, status,
                    created_at, updated_at
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid,
                    'timeout worker parity', 'ACTIVE',
                    clock_timestamp(), clock_timestamp()
                )
                """,
                (offering_id, provider_player_id, sku[0]),
            )
        connection.commit()

    return Seed(
        customer_id=customer[0],
        sku_id=sku[0],
        provider_user_id=provider_user_id,
        provider_player_id=provider_player_id,
        platform_user_id=platform[0],
    )


def create_paid_claimed(
    go_base: str,
    seed: Seed,
    label: str,
) -> dict[str, Any]:
    customer_headers = {"X-User-Id": seed.customer_id}
    player_headers = {"X-User-Id": seed.provider_user_id}

    created = expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={
                "sku_id": seed.sku_id,
                "quantity": 1,
                "remark": label,
            },
        ),
        201,
        f"create {label}",
    ).body
    paid = expect(
        call(
            go_base,
            f"/api/v1/orders/{created['id']}/mock-pay",
            method="POST",
            headers={
                **customer_headers,
                "Idempotency-Key": f"{label}-{uuid.uuid4().hex}",
            },
        ),
        200,
        f"pay {label}",
    ).body
    return expect(
        call(
            go_base,
            f"/api/v1/player/orders/{created['id']}/claim",
            method="POST",
            headers=player_headers,
            body={"expected_version": paid["version"]},
        ),
        200,
        f"claim {label}",
    ).body


def finish_order(
    go_base: str,
    seed: Seed,
    claimed: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    player_headers = {"X-User-Id": seed.provider_user_id}
    expect(
        call(
            go_base,
            f"/api/v1/player/orders/{claimed['id']}/start",
            method="POST",
            headers=player_headers,
        ),
        200,
        f"start {label}",
    )
    return expect(
        call(
            go_base,
            f"/api/v1/player/orders/{claimed['id']}/finish",
            method="POST",
            headers=player_headers,
        ),
        200,
        f"finish {label}",
    ).body


def age_finish_requests(order_ids: list[str], minutes: int) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orders
                SET finish_requested_at =
                    clock_timestamp() - (%s * interval '1 minute')
                WHERE id = ANY(%s::uuid[])
                """,
                (minutes, order_ids),
            )
        connection.commit()


def age_acceptances(order_ids: list[str], minutes: int) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orders
                SET accepted_at =
                    clock_timestamp() - (%s * interval '1 minute')
                WHERE id = ANY(%s::uuid[])
                """,
                (minutes, order_ids),
            )
        connection.commit()


def wallet_state(user_id: str) -> tuple[int, int]:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT available_balance, version
                FROM wallets
                WHERE user_id = %s::uuid
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    return (0, 0) if row is None else (int(row[0]), int(row[1]))


def stop_fastapi_reference(base: str) -> None:
    path = "/tmp/fastapi.pid"
    if not os.path.exists(path):
        return
    try:
        pid = int(open(path, encoding="utf-8").read().strip())
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            call(base, "/readyz")
        except OSError:
            return
        time.sleep(0.05)
    raise AssertionError("FastAPI reference did not stop before timeout-worker parity")


def start_worker(index: int) -> tuple[subprocess.Popen[bytes], Any]:
    env = os.environ.copy()
    env["ORDER_TIMEOUT_SCAN_SECONDS"] = "1"
    env["ORDER_TIMEOUT_BATCH_SIZE"] = "5"
    env["FINISH_CONFIRM_TIMEOUT_SECONDS"] = "1800"
    env["ASSIGNMENT_START_TIMEOUT_SECONDS"] = "600"
    env["OUTBOX_POLL_INTERVAL_MS"] = "25"
    env["OUTBOX_BATCH_SIZE"] = "20"
    log = open(f"/tmp/api-go-timeout-worker-{index}.log", "wb")
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


def wait_processed(
    auto_ids: list[str],
    requeue_ids: list[str],
    timeout: float = 25.0,
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with psycopg.connect(dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM orders
                    WHERE id = ANY(%s::uuid[])
                      AND status = 'SETTLED'
                    """,
                    (auto_ids,),
                )
                settled = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM orders
                    WHERE id = ANY(%s::uuid[])
                      AND status = 'MATCHING'
                    """,
                    (requeue_ids,),
                )
                matching = int(cursor.fetchone()[0])
        if settled == len(auto_ids) and matching == len(requeue_ids):
            return
        time.sleep(0.1)
    raise AssertionError(
        f"timeout workers did not finish: "
        f"settled={settled}/{len(auto_ids)} "
        f"matching={matching}/{len(requeue_ids)}"
    )


def verify_auto_confirm(
    orders: list[dict[str, Any]],
    seed: Seed,
    provider_before: tuple[int, int],
    platform_before: tuple[int, int],
) -> None:
    ids = [order["id"] for order in orders]
    total_provider = sum(order["player_amount"] for order in orders)
    total_platform = sum(order["platform_fee"] for order in orders)

    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, status, version
                FROM orders
                WHERE id = ANY(%s::uuid[])
                ORDER BY id
                """,
                (ids,),
            )
            states = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            for order in orders:
                expected = ("SETTLED", order["version"] + 2)
                if states.get(order["id"]) != expected:
                    raise AssertionError(
                        f"auto-confirm state {order['id']}="
                        f"{states.get(order['id'])!r} want={expected!r}"
                    )

            cursor.execute(
                """
                SELECT order_id::text, count(*)
                FROM settlements
                WHERE order_id = ANY(%s::uuid[])
                GROUP BY order_id
                """,
                (ids,),
            )
            if {row[0]: row[1] for row in cursor.fetchall()} != {
                order_id: 1 for order_id in ids
            }:
                raise AssertionError("auto-confirm settlement rows are not exactly once")

            cursor.execute(
                """
                SELECT biz_id, count(*)
                FROM ledger_entries
                WHERE biz_type = 'ORDER_SETTLEMENT'
                  AND biz_id = ANY(%s)
                GROUP BY biz_id
                """,
                (ids,),
            )
            if {row[0]: row[1] for row in cursor.fetchall()} != {
                order_id: 2 for order_id in ids
            }:
                raise AssertionError("auto-confirm ledger rows are not exactly two")

            cursor.execute(
                """
                SELECT
                    order_id::text,
                    event_type,
                    count(*),
                    min(payload_json)
                FROM order_events
                WHERE order_id = ANY(%s::uuid[])
                  AND event_type IN (
                    'AUTO_CONFIRM_FINISH',
                    'USER_CONFIRMED_FINISH',
                    'SETTLEMENT_COMPLETED'
                  )
                GROUP BY order_id, event_type
                """,
                (ids,),
            )
            events: dict[tuple[str, str], tuple[int, Any]] = {
                (row[0], row[1]): (int(row[2]), row[3])
                for row in cursor.fetchall()
            }
            for order_id in ids:
                auto = events.get((order_id, "AUTO_CONFIRM_FINISH"))
                settled = events.get((order_id, "SETTLEMENT_COMPLETED"))
                if auto is None or auto[0] != 1:
                    raise AssertionError(f"auto-confirm evidence missing for {order_id}")
                if auto[1].get("timeoutSeconds") != 1800:
                    raise AssertionError(f"auto-confirm timeout payload={auto[1]!r}")
                if not auto[1].get("finishRequestedAt"):
                    raise AssertionError(f"auto-confirm timestamp payload={auto[1]!r}")
                if settled is None or settled[0] != 1:
                    raise AssertionError(f"settlement evidence missing for {order_id}")
                if (order_id, "USER_CONFIRMED_FINISH") in events:
                    raise AssertionError(
                        f"user-confirm evidence leaked into auto-confirm {order_id}"
                    )

    provider_after = wallet_state(seed.provider_user_id)
    platform_after = wallet_state(seed.platform_user_id)
    if provider_after != (
        provider_before[0] + total_provider,
        provider_before[1] + len(orders),
    ):
        raise AssertionError(
            f"provider wallet delta={provider_before}->{provider_after}, "
            f"expected amount+={total_provider}, version+={len(orders)}"
        )
    if platform_after != (
        platform_before[0] + total_platform,
        platform_before[1] + len(orders),
    ):
        raise AssertionError(
            f"platform wallet delta={platform_before}->{platform_after}, "
            f"expected amount+={total_platform}, version+={len(orders)}"
        )


def verify_requeues(
    orders: list[dict[str, Any]],
    seed: Seed,
    redis_client: redis.Redis,
) -> None:
    ids = [order["id"] for order in orders]
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id::text,
                    status,
                    designated_player_id::text,
                    version,
                    game_id::text
                FROM orders
                WHERE id = ANY(%s::uuid[])
                ORDER BY id
                """,
                (ids,),
            )
            states = {
                row[0]: (row[1], row[2], row[3], row[4])
                for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT
                    order_id::text,
                    status,
                    released_at IS NOT NULL,
                    player_id::text
                FROM order_assignments
                WHERE order_id = ANY(%s::uuid[])
                ORDER BY order_id
                """,
                (ids,),
            )
            assignments = {
                row[0]: (row[1], row[2], row[3])
                for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT order_id::text, event_type, payload_json
                FROM order_events
                WHERE order_id = ANY(%s::uuid[])
                  AND event_type = 'ASSIGNMENT_TIMED_OUT'
                ORDER BY order_id
                """,
                (ids,),
            )
            events = {row[0]: row[2] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT aggregate_id, count(*)
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = ANY(%s)
                  AND event_type = 'ASSIGNMENT_TIMED_OUT'
                GROUP BY aggregate_id
                """,
                (ids,),
            )
            outbox = {row[0]: int(row[1]) for row in cursor.fetchall()}

    for order in orders:
        state = states.get(order["id"])
        if state is None:
            raise AssertionError(f"requeued order missing: {order['id']}")
        if state[:3] != ("MATCHING", None, order["version"] + 1):
            raise AssertionError(f"unexpected requeue state {order['id']}={state!r}")
        assignment = assignments.get(order["id"])
        if assignment != ("RELEASED", True, seed.provider_player_id):
            raise AssertionError(
                f"assignment not released {order['id']}={assignment!r}"
            )
        payload = events.get(order["id"])
        if payload != {
            "playerId": seed.provider_player_id,
            "timeoutSeconds": 600,
        }:
            raise AssertionError(
                f"assignment timeout evidence {order['id']}={payload!r}"
            )
        if outbox.get(order["id"]) != 1:
            raise AssertionError(
                f"assignment timeout outbox count {order['id']}="
                f"{outbox.get(order['id'])!r}"
            )
        game_id = state[3]
        score = redis_client.zscore(f"order_pool:{game_id}", order["id"])
        if score is None:
            raise AssertionError(
                f"requeued order missing Redis pool acceleration: {order['id']}"
            )


def verify_recent_controls(
    recent_finish_id: str,
    recent_accepted_id: str,
) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM orders WHERE id = %s::uuid",
                (recent_finish_id,),
            )
            if cursor.fetchone() != ("FINISH_REQUESTED",):
                raise AssertionError("recent finish request was auto-confirmed early")

            cursor.execute(
                """
                SELECT o.status, a.status
                FROM orders o
                JOIN order_assignments a
                  ON a.order_id = o.id
                 AND a.status = 'ACTIVE'
                WHERE o.id = %s::uuid
                """,
                (recent_accepted_id,),
            )
            if cursor.fetchone() != ("ACCEPTED", "ACTIVE"):
                raise AssertionError("recent assignment was released early")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()

    stop_fastapi_reference(args.python_base)
    seed = seed_context()

    auto_orders: list[dict[str, Any]] = []
    requeue_orders: list[dict[str, Any]] = []
    for index in range(args.count):
        claimed = create_paid_claimed(
            args.go_base,
            seed,
            f"timeout-auto-{index}",
        )
        auto_orders.append(
            finish_order(
                args.go_base,
                seed,
                claimed,
                f"timeout-auto-{index}",
            )
        )
        requeue_orders.append(
            create_paid_claimed(
                args.go_base,
                seed,
                f"timeout-requeue-{index}",
            )
        )

    recent_finish_claimed = create_paid_claimed(
        args.go_base,
        seed,
        "timeout-recent-finish",
    )
    recent_finish = finish_order(
        args.go_base,
        seed,
        recent_finish_claimed,
        "timeout-recent-finish",
    )
    recent_accepted = create_paid_claimed(
        args.go_base,
        seed,
        "timeout-recent-assignment",
    )

    age_finish_requests(
        [order["id"] for order in auto_orders],
        31,
    )
    age_finish_requests([recent_finish["id"]], 10)
    age_acceptances(
        [order["id"] for order in requeue_orders],
        11,
    )
    age_acceptances([recent_accepted["id"]], 5)

    provider_before = wallet_state(seed.provider_user_id)
    platform_before = wallet_state(seed.platform_user_id)

    redis_client = redis.Redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )
    redis_client.ping()

    workers: list[tuple[subprocess.Popen[bytes], Any]] = []
    try:
        workers = [start_worker(1), start_worker(2)]
        for process, _log in workers:
            time.sleep(0.05)
            if process.poll() is not None:
                raise AssertionError(
                    f"timeout worker exited early with {process.returncode}"
                )

        wait_processed(
            [order["id"] for order in auto_orders],
            [order["id"] for order in requeue_orders],
        )

        verify_auto_confirm(
            auto_orders,
            seed,
            provider_before,
            platform_before,
        )
        verify_requeues(requeue_orders, seed, redis_client)
        verify_recent_controls(
            recent_finish["id"],
            recent_accepted["id"],
        )
        print(
            "PASS two Go workers auto-confirm and requeue due orders "
            "without duplicate money/evidence"
        )
    finally:
        redis_client.close()
        for process, log in workers:
            stop_worker(process, log)

    print("M5.3 order timeout worker parity PASS")
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
        print(f"M5.3 order timeout parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
