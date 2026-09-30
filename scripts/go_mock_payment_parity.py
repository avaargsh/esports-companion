#!/usr/bin/env python3
"""Verify M3.5 mock payment parity, idempotency and concurrency."""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
import uuid
from typing import Any

import psycopg

from go_claim_parity import Response, call, dsn, expect


def create_order(
    go_base: str,
    headers: dict[str, str],
    sku_id: str,
    label: str,
    *,
    offering_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"quantity": 1, "remark": label}
    if offering_id is None:
        body["sku_id"] = sku_id
    else:
        body["offering_id"] = offering_id
    return expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=headers,
            body=body,
        ),
        201,
        f"create {label}",
    ).body


def pay(
    base: str,
    order_id: str,
    headers: dict[str, str],
    key: str,
    label: str,
) -> Response:
    return call(
        base,
        f"/api/v1/orders/{order_id}/mock-pay",
        method="POST",
        headers={**headers, "Idempotency-Key": key},
    )


def seed_designated_provider(sku_id: str) -> tuple[str, str, str]:
    user_id = str(uuid.uuid4())
    player_id = str(uuid.uuid4())
    offering_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex[:8]
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (
                    id, openid, unionid, nickname, avatar_url, phone,
                    role, status, created_at, updated_at
                )
                VALUES (
                    %s::uuid, NULL, NULL, %s, NULL, NULL,
                    'USER', 'ACTIVE', now(), now()
                )
                """,
                (user_id, f"payment-provider-{suffix}"),
            )
            cursor.execute(
                """
                INSERT INTO player_profiles (
                    id, user_id, display_name, bio, gender,
                    verification_status, service_status,
                    rating, order_count, created_at, updated_at
                )
                VALUES (
                    %s::uuid, %s::uuid, %s, '', NULL,
                    'APPROVED', 'AVAILABLE',
                    0, 0, now(), now()
                )
                """,
                (player_id, user_id, f"Payment Provider {suffix}"),
            )
            cursor.execute(
                """
                INSERT INTO provider_offerings (
                    id, player_id, sku_id, price_override,
                    description, status, created_at, updated_at
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, NULL,
                    'mock payment parity', 'ACTIVE', now(), now()
                )
                """,
                (offering_id, player_id, sku_id),
            )
        connection.commit()
    return user_id, player_id, offering_id


def payment_projection(order: dict[str, Any]) -> dict[str, Any]:
    return {
        key: order[key]
        for key in (
            "id",
            "user_id",
            "game_id",
            "sku_id",
            "designated_player_id",
            "status",
            "quantity",
            "unit_price",
            "total_amount",
            "player_amount",
            "platform_fee",
            "version",
        )
    }


def verify_payment(
    order: dict[str, Any],
    *,
    expected_key: str | None,
    expected_status: str,
    expected_version: int,
    designated_player_id: str | None = None,
) -> None:
    order_id = order["id"]
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, version, paid_at IS NOT NULL
                FROM orders
                WHERE id = %s::uuid
                """,
                (order_id,),
            )
            state = cursor.fetchone()
            if state != (expected_status, expected_version, True):
                raise AssertionError(
                    f"payment order state got={state!r} "
                    f"want={(expected_status, expected_version, True)!r}"
                )

            cursor.execute(
                """
                SELECT
                    provider,
                    provider_txn_id,
                    idempotency_key,
                    amount,
                    status,
                    raw_payload
                FROM payment_transactions
                WHERE order_id = %s::uuid
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            transactions = cursor.fetchall()
            if len(transactions) != 1:
                raise AssertionError(
                    f"expected one payment transaction, got {transactions!r}"
                )
            provider, provider_txn_id, key, amount, status, raw_payload = transactions[0]
            if provider != "MOCK" or not provider_txn_id.startswith("mock_"):
                raise AssertionError(f"unexpected mock transaction: {transactions[0]!r}")
            if expected_key is not None and key != expected_key:
                raise AssertionError(f"idempotency key = {key!r}, want {expected_key!r}")
            if amount != order["total_amount"] or status != "SUCCESS":
                raise AssertionError(f"unexpected mock amount/status: {transactions[0]!r}")
            if raw_payload != {
                "provider": {"mode": "mock", "idempotencyKey": key},
                "clientPayload": {},
            }:
                raise AssertionError(f"unexpected mock raw payload: {raw_payload!r}")

            cursor.execute(
                """
                SELECT
                    event_type,
                    from_status,
                    to_status,
                    actor_type,
                    actor_id,
                    payload_json
                FROM order_events
                WHERE order_id = %s::uuid
                  AND event_type IN (
                    'PAYMENT_SUCCESS',
                    'ORDER_ENTERED_MATCHING',
                    'DESIGNATED_PLAYER_ASSIGNED'
                  )
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            events = cursor.fetchall()
            expected_events: list[tuple[Any, ...]] = [
                (
                    "PAYMENT_SUCCESS",
                    "WAITING_PAYMENT",
                    "PAID",
                    "PAYMENT",
                    None,
                    {"provider": "MOCK"},
                ),
                (
                    "ORDER_ENTERED_MATCHING",
                    "PAID",
                    "MATCHING",
                    "SYSTEM",
                    None,
                    {},
                ),
            ]
            if designated_player_id is not None:
                expected_events.append(
                    (
                        "DESIGNATED_PLAYER_ASSIGNED",
                        "MATCHING",
                        "ACCEPTED",
                        "USER",
                        order["user_id"],
                        {"playerId": designated_player_id},
                    )
                )
            if events != expected_events:
                raise AssertionError(
                    f"payment event mismatch got={events!r} want={expected_events!r}"
                )

            cursor.execute(
                """
                SELECT event_type, payload_json
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type IN (
                    'PAYMENT_SUCCESS',
                    'ORDER_ENTERED_MATCHING',
                    'DESIGNATED_PLAYER_ASSIGNED'
                  )
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            outbox = cursor.fetchall()
            expected_outbox = [
                (
                    "PAYMENT_SUCCESS",
                    {
                        "orderId": order_id,
                        "status": "PAID",
                        "provider": "MOCK",
                    },
                ),
                (
                    "ORDER_ENTERED_MATCHING",
                    {"orderId": order_id, "status": "MATCHING"},
                ),
            ]
            if designated_player_id is not None:
                expected_outbox.append(
                    (
                        "DESIGNATED_PLAYER_ASSIGNED",
                        {
                            "orderId": order_id,
                            "status": "ACCEPTED",
                            "playerId": designated_player_id,
                        },
                    )
                )
            if outbox != expected_outbox:
                raise AssertionError(
                    f"payment outbox mismatch got={outbox!r} want={expected_outbox!r}"
                )

            if designated_player_id is not None:
                cursor.execute(
                    """
                    SELECT player_id::text, assigned_by
                    FROM order_assignments
                    WHERE order_id = %s::uuid
                      AND status = 'ACTIVE'
                    """,
                    (order_id,),
                )
                assignments = cursor.fetchall()
                if assignments != [(designated_player_id, "USER")]:
                    raise AssertionError(
                        f"designated assignment mismatch: {assignments!r}"
                    )


def assert_error_same(
    python_base: str,
    go_base: str,
    order_id: str,
    headers: dict[str, str],
    key: str,
    *,
    status: int,
    detail: str,
    label: str,
) -> None:
    for base, runtime in ((python_base, "FastAPI"), (go_base, "Go")):
        response = expect(
            pay(base, order_id, headers, key, f"{runtime} {label}"),
            status,
            f"{runtime} {label}",
        )
        if response.body.get("detail") != detail:
            raise AssertionError(
                f"{runtime} {label}: detail={response.body!r}, want={detail!r}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    bootstrap = expect(
        call(args.python_base, "/api/v1/dev/bootstrap"),
        200,
        "bootstrap",
    ).body
    customer_headers = {"X-User-Id": bootstrap["customerUserId"]}
    other_headers = {"X-User-Id": bootstrap["playerUserId"]}
    sku_id = bootstrap["games"][0]["skus"][0]["id"]

    pooled = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-mock-payment-happy",
    )
    key = f"go-mock-{uuid.uuid4().hex}"
    paid = expect(
        pay(args.go_base, pooled["id"], customer_headers, key, "Go mock payment"),
        200,
        "Go mock payment",
    ).body
    if paid["status"] != "MATCHING" or paid["version"] != pooled["version"] + 2:
        raise AssertionError(f"unexpected pooled payment projection: {paid!r}")

    python_read = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{paid['id']}",
            headers=customer_headers,
        ),
        200,
        "FastAPI reads Go payment",
    ).body
    if payment_projection(python_read) != payment_projection(paid):
        raise AssertionError(
            "FastAPI did not observe Go mock payment "
            f"FastAPI={payment_projection(python_read)!r} "
            f"Go={payment_projection(paid)!r}"
        )
    verify_payment(
        paid,
        expected_key=key,
        expected_status="MATCHING",
        expected_version=pooled["version"] + 2,
    )
    print("PASS pooled Go mock payment + durable evidence")

    go_replay = expect(
        pay(args.go_base, pooled["id"], customer_headers, key, "Go payment replay"),
        200,
        "Go payment replay",
    ).body
    py_replay = expect(
        pay(
            args.python_base,
            pooled["id"],
            customer_headers,
            key,
            "FastAPI payment replay",
        ),
        200,
        "FastAPI payment replay",
    ).body
    if payment_projection(go_replay) != payment_projection(paid):
        raise AssertionError(f"Go replay changed order: {go_replay!r}")
    if payment_projection(py_replay) != payment_projection(paid):
        raise AssertionError(f"FastAPI replay changed order: {py_replay!r}")
    verify_payment(
        paid,
        expected_key=key,
        expected_status="MATCHING",
        expected_version=pooled["version"] + 2,
    )
    print("PASS cross-runtime mock payment replay is idempotent")

    assert_error_same(
        args.python_base,
        args.go_base,
        pooled["id"],
        customer_headers,
        f"different-{uuid.uuid4().hex}",
        status=409,
        detail="ORDER_NOT_WAITING_PAYMENT",
        label="new key after payment",
    )

    second = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-mock-payment-key-reuse",
    )
    assert_error_same(
        args.python_base,
        args.go_base,
        second["id"],
        customer_headers,
        key,
        status=409,
        detail="IDEMPOTENCY_KEY_REUSED",
        label="idempotency key reused across orders",
    )

    wrong_owner = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-mock-payment-wrong-owner",
    )
    assert_error_same(
        args.python_base,
        args.go_base,
        wrong_owner["id"],
        other_headers,
        f"wrong-owner-{uuid.uuid4().hex}",
        status=403,
        detail="ORDER_NOT_OWNED",
        label="wrong owner",
    )

    _provider_user, provider_player, offering_id = seed_designated_provider(sku_id)
    designated = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-designated-mock-payment",
        offering_id=offering_id,
    )
    designated_key = f"go-designated-{uuid.uuid4().hex}"
    designated_paid = expect(
        pay(
            args.go_base,
            designated["id"],
            customer_headers,
            designated_key,
            "Go designated mock payment",
        ),
        200,
        "Go designated mock payment",
    ).body
    if (
        designated_paid["status"] != "ACCEPTED"
        or designated_paid["version"] != designated["version"] + 3
    ):
        raise AssertionError(
            f"unexpected designated payment projection: {designated_paid!r}"
        )
    verify_payment(
        designated_paid,
        expected_key=designated_key,
        expected_status="ACCEPTED",
        expected_version=designated["version"] + 3,
        designated_player_id=provider_player,
    )
    print("PASS designated mock payment atomically assigns provider")

    same_key_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-mock-payment-concurrent-same-key",
    )
    same_key = f"same-key-{uuid.uuid4().hex}"

    def same_key_pay(_index: int) -> Response:
        return pay(
            args.go_base,
            same_key_order["id"],
            customer_headers,
            same_key,
            "concurrent same-key payment",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        same_key_responses = list(executor.map(same_key_pay, range(20)))
    bad_same = [
        response
        for response in same_key_responses
        if response.status != 200
        or response.body.get("status") != "MATCHING"
        or response.body.get("version") != same_key_order["version"] + 2
    ]
    if bad_same:
        raise AssertionError(f"same-key concurrent payment failures: {bad_same!r}")
    verify_payment(
        same_key_responses[0].body,
        expected_key=same_key,
        expected_status="MATCHING",
        expected_version=same_key_order["version"] + 2,
    )
    print("PASS 20-way same-key mock payment is exactly-once")

    distinct_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-mock-payment-concurrent-distinct-key",
    )

    def distinct_key_pay(index: int) -> Response:
        return pay(
            args.go_base,
            distinct_order["id"],
            customer_headers,
            f"distinct-{index}-{uuid.uuid4().hex}",
            "concurrent distinct-key payment",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        distinct_responses = list(executor.map(distinct_key_pay, range(20)))
    winners = [r for r in distinct_responses if r.status == 200]
    conflicts = [r for r in distinct_responses if r.status == 409]
    if len(winners) != 1 or len(conflicts) != 19:
        raise AssertionError(
            f"distinct-key race winners={len(winners)} conflicts={len(conflicts)} "
            f"responses={distinct_responses!r}"
        )
    if any(r.body.get("detail") != "ORDER_NOT_WAITING_PAYMENT" for r in conflicts):
        raise AssertionError(f"unexpected distinct-key conflicts: {conflicts!r}")
    verify_payment(
        winners[0].body,
        expected_key=None,
        expected_status="MATCHING",
        expected_version=distinct_order["version"] + 2,
    )
    print("PASS 20-way distinct-key payment has one winner")

    missing = "00000000-0000-0000-0000-000000000000"
    assert_error_same(
        args.python_base,
        args.go_base,
        missing,
        customer_headers,
        f"missing-{uuid.uuid4().hex}",
        status=404,
        detail="ORDER_NOT_FOUND",
        label="missing order",
    )

    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        invalid = expect(
            pay(
                base,
                "not-a-uuid",
                customer_headers,
                f"invalid-{uuid.uuid4().hex}",
                f"{runtime} invalid UUID",
            ),
            422,
            f"{runtime} invalid UUID",
        )
        if not invalid.body:
            raise AssertionError(f"{runtime} invalid UUID missing validation body")

        missing_header = expect(
            call(
                base,
                f"/api/v1/orders/{wrong_owner['id']}/mock-pay",
                method="POST",
                headers=customer_headers,
            ),
            422,
            f"{runtime} missing idempotency header",
        )
        detail = missing_header.body.get("detail")
        if not detail or detail[0].get("type") != "missing":
            raise AssertionError(
                f"{runtime} missing-header validation mismatch: {missing_header.body!r}"
            )

    print("M3.5 mock payment parity PASS")
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
        print(f"M3.5 mock payment parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
