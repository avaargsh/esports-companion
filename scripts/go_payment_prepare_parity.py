#!/usr/bin/env python3
"""Verify M4.1 payment-prepare interoperability and idempotency."""

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
) -> dict[str, Any]:
    return expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=headers,
            body={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": label,
            },
        ),
        201,
        f"create {label}",
    ).body


def prepare(
    base: str,
    order_id: str,
    headers: dict[str, str],
    key: str,
) -> Response:
    return call(
        base,
        f"/api/v1/orders/{order_id}/payments",
        method="POST",
        headers={**headers, "Idempotency-Key": key},
    )


def assert_prepare_shape(
    body: dict[str, Any],
    *,
    order_id: str,
    replayed: bool,
) -> None:
    expected = {
        "order_id": order_id,
        "order_status": "MATCHING",
        "provider": "MOCK",
        "payment_status": "SUCCESS",
        "client_payload": {},
        "replayed": replayed,
    }
    if body != expected:
        raise AssertionError(f"prepare body got={body!r} want={expected!r}")


def transaction_count(order_id: str) -> int:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM payment_transactions
                WHERE order_id = %s::uuid
                """,
                (order_id,),
            )
            row = cursor.fetchone()
    return int(row[0])


def transaction_key(order_id: str) -> str:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT idempotency_key
                FROM payment_transactions
                WHERE order_id = %s::uuid
                """,
                (order_id,),
            )
            row = cursor.fetchone()
    if row is None:
        raise AssertionError("payment transaction missing")
    return str(row[0])


def assert_same_error(
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
            prepare(base, order_id, headers, key),
            status,
            f"{runtime} {label}",
        )
        if response.body.get("detail") != detail:
            raise AssertionError(
                f"{runtime} {label}: got={response.body!r} want detail={detail!r}"
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

    go_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-payment-prepare",
    )
    go_key = f"go-prepare-{uuid.uuid4().hex}"
    first = expect(
        prepare(args.go_base, go_order["id"], customer_headers, go_key),
        200,
        "Go payment prepare",
    ).body
    assert_prepare_shape(first, order_id=go_order["id"], replayed=False)
    if transaction_count(go_order["id"]) != 1:
        raise AssertionError("Go prepare did not create exactly one transaction")

    python_read = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{go_order['id']}",
            headers=customer_headers,
        ),
        200,
        "FastAPI reads Go prepared order",
    ).body
    if python_read["status"] != "MATCHING" or python_read["version"] != go_order["version"] + 2:
        raise AssertionError(f"FastAPI did not observe Go prepare: {python_read!r}")

    py_replay = expect(
        prepare(args.python_base, go_order["id"], customer_headers, go_key),
        200,
        "FastAPI replays Go prepare",
    ).body
    go_replay = expect(
        prepare(args.go_base, go_order["id"], customer_headers, go_key),
        200,
        "Go replays Go prepare",
    ).body
    assert_prepare_shape(py_replay, order_id=go_order["id"], replayed=True)
    assert_prepare_shape(go_replay, order_id=go_order["id"], replayed=True)
    if transaction_count(go_order["id"]) != 1:
        raise AssertionError("cross-runtime replay duplicated payment transaction")
    print("PASS Go prepare + FastAPI/Go replay")

    py_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "python-payment-prepare",
    )
    py_key = f"py-prepare-{uuid.uuid4().hex}"
    py_first = expect(
        prepare(args.python_base, py_order["id"], customer_headers, py_key),
        200,
        "FastAPI payment prepare",
    ).body
    assert_prepare_shape(py_first, order_id=py_order["id"], replayed=False)
    go_reads_py = expect(
        prepare(args.go_base, py_order["id"], customer_headers, py_key),
        200,
        "Go replays FastAPI prepare",
    ).body
    assert_prepare_shape(go_reads_py, order_id=py_order["id"], replayed=True)
    if transaction_count(py_order["id"]) != 1:
        raise AssertionError("Go replay duplicated FastAPI payment transaction")
    print("PASS FastAPI prepare + Go replay")

    reused_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "payment-key-reuse",
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        reused_order["id"],
        customer_headers,
        go_key,
        status=409,
        detail="IDEMPOTENCY_KEY_REUSED",
        label="cross-order idempotency reuse",
    )

    assert_same_error(
        args.python_base,
        args.go_base,
        go_order["id"],
        customer_headers,
        f"new-key-{uuid.uuid4().hex}",
        status=409,
        detail="ORDER_NOT_WAITING_PAYMENT",
        label="new key after success",
    )

    wrong_owner_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "payment-wrong-owner",
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        wrong_owner_order["id"],
        other_headers,
        f"wrong-owner-{uuid.uuid4().hex}",
        status=403,
        detail="ORDER_NOT_OWNED",
        label="wrong owner",
    )

    same_key_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "payment-same-key-race",
    )
    same_key = f"same-key-{uuid.uuid4().hex}"

    def same_key_prepare(_index: int) -> Response:
        return prepare(
            args.go_base,
            same_key_order["id"],
            customer_headers,
            same_key,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        same_responses = list(executor.map(same_key_prepare, range(20)))
    if any(response.status != 200 for response in same_responses):
        raise AssertionError(f"same-key prepare race failed: {same_responses!r}")
    first_count = sum(
        1 for response in same_responses
        if response.body.get("replayed") is False
    )
    replay_count = sum(
        1 for response in same_responses
        if response.body.get("replayed") is True
    )
    if first_count != 1 or replay_count != 19:
        raise AssertionError(
            f"same-key replay split first={first_count} replay={replay_count}"
        )
    if transaction_count(same_key_order["id"]) != 1:
        raise AssertionError("same-key race created duplicate transactions")
    if transaction_key(same_key_order["id"]) != same_key:
        raise AssertionError("same-key race persisted unexpected idempotency key")
    print("PASS 20-way same-key prepare exactly once")

    distinct_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "payment-distinct-key-race",
    )

    def distinct_prepare(index: int) -> Response:
        return prepare(
            args.go_base,
            distinct_order["id"],
            customer_headers,
            f"distinct-{index}-{uuid.uuid4().hex}",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        distinct_responses = list(executor.map(distinct_prepare, range(20)))
    winners = [r for r in distinct_responses if r.status == 200]
    conflicts = [r for r in distinct_responses if r.status == 409]
    if len(winners) != 1 or len(conflicts) != 19:
        raise AssertionError(
            f"distinct prepare winners={len(winners)} conflicts={len(conflicts)}"
        )
    if any(r.body.get("detail") != "ORDER_NOT_WAITING_PAYMENT" for r in conflicts):
        raise AssertionError(f"unexpected distinct prepare conflicts: {conflicts!r}")
    if transaction_count(distinct_order["id"]) != 1:
        raise AssertionError("distinct-key race created duplicate transactions")
    print("PASS 20-way distinct-key prepare has one winner")

    missing = "00000000-0000-0000-0000-000000000000"
    assert_same_error(
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
            prepare(
                base,
                "not-a-uuid",
                customer_headers,
                f"invalid-{uuid.uuid4().hex}",
            ),
            422,
            f"{runtime} invalid UUID",
        )
        if not invalid.body:
            raise AssertionError(f"{runtime} invalid UUID missing body")

        missing_header = expect(
            call(
                base,
                f"/api/v1/orders/{wrong_owner_order['id']}/payments",
                method="POST",
                headers=customer_headers,
            ),
            422,
            f"{runtime} missing Idempotency-Key",
        )
        detail = missing_header.body.get("detail")
        if not detail or detail[0].get("type") != "missing":
            raise AssertionError(
                f"{runtime} missing header body mismatch: {missing_header.body!r}"
            )

    print("M4.1 payment prepare parity PASS")
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
        print(f"M4.1 payment prepare parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
