#!/usr/bin/env python3
"""Verify M4.3 refund submit interoperability and recovery semantics."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import uuid
from typing import Any

import psycopg

from go_claim_parity import Response, call, dsn, expect


def create_order(
    go_base: str,
    customer_headers: dict[str, str],
    sku_id: str,
    label: str,
    *,
    pay: bool = True,
) -> dict[str, Any]:
    order = expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={"sku_id": sku_id, "quantity": 1, "remark": label},
        ),
        201,
        f"create {label}",
    ).body
    if not pay:
        return order
    return expect(
        call(
            go_base,
            f"/api/v1/orders/{order['id']}/mock-pay",
            method="POST",
            headers={
                **customer_headers,
                "Idempotency-Key": f"{label}-{uuid.uuid4().hex}",
            },
        ),
        200,
        f"pay {label}",
    ).body


def seed_refund(
    order: dict[str, Any],
    *,
    customer_id: str,
    admin_id: str,
    status: str = "PENDING",
    order_status: str = "REFUNDING",
    out_refund_no: str | None = None,
) -> str:
    dispute_id = str(uuid.uuid4())
    refund_id = str(uuid.uuid4())
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orders
                SET status = %s,
                    version = version + 1,
                    updated_at = clock_timestamp()
                WHERE id = %s::uuid
                """,
                (order_status, order["id"]),
            )
            cursor.execute(
                """
                INSERT INTO disputes (
                    id,
                    order_id,
                    status,
                    opened_by_user_id,
                    opened_by_role,
                    reason_code,
                    description,
                    held_amount,
                    resolution,
                    resolved_by_user_id,
                    idempotency_key
                )
                VALUES (
                    %s::uuid,
                    %s::uuid,
                    'RESOLVING',
                    %s::uuid,
                    'USER',
                    'OTHER',
                    'refund submit parity',
                    %s,
                    'REFUND_CUSTOMER',
                    %s::uuid,
                    %s
                )
                """,
                (
                    dispute_id,
                    order["id"],
                    customer_id,
                    order["total_amount"],
                    admin_id,
                    f"dispute-{uuid.uuid4().hex}",
                ),
            )
            cursor.execute(
                """
                INSERT INTO refunds (
                    id,
                    order_id,
                    dispute_id,
                    amount,
                    status,
                    provider,
                    out_refund_no,
                    idempotency_key,
                    raw_payload
                )
                VALUES (
                    %s::uuid,
                    %s::uuid,
                    %s::uuid,
                    %s,
                    %s,
                    'MANUAL',
                    %s,
                    %s,
                    '{}'::json
                )
                """,
                (
                    refund_id,
                    order["id"],
                    dispute_id,
                    order["total_amount"],
                    status,
                    out_refund_no,
                    f"refund-{uuid.uuid4().hex}",
                ),
            )
        connection.commit()
    return refund_id


def submit(
    base: str,
    refund_id: str,
    admin_headers: dict[str, str],
) -> Response:
    return call(
        base,
        f"/api/v1/admin/refunds/{refund_id}/submit",
        method="POST",
        headers=admin_headers,
    )


def refund_row(refund_id: str) -> dict[str, Any]:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id::text,
                    order_id::text,
                    dispute_id::text,
                    amount,
                    status,
                    provider,
                    out_refund_no,
                    provider_refund_id,
                    failure_reason,
                    raw_payload,
                    completed_at
                FROM refunds
                WHERE id = %s::uuid
                """,
                (refund_id,),
            )
            row = cursor.fetchone()
    if row is None:
        raise AssertionError("refund row missing")
    return {
        "id": row[0],
        "order_id": row[1],
        "dispute_id": row[2],
        "amount": row[3],
        "status": row[4],
        "provider": row[5],
        "out_refund_no": row[6],
        "provider_refund_id": row[7],
        "failure_reason": row[8],
        "raw_payload": row[9],
        "completed_at": row[10],
    }


def order_status(order_id: str) -> str:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM orders WHERE id = %s::uuid",
                (order_id,),
            )
            row = cursor.fetchone()
    if row is None:
        raise AssertionError("order missing")
    return str(row[0])


def expected_out_refund_no(refund_id: str) -> str:
    return "RFD_" + refund_id.replace("-", "")


def assert_manual_result(
    body: dict[str, Any],
    *,
    refund_id: str,
    order_id: str,
) -> None:
    if body["id"] != refund_id or body["order_id"] != order_id:
        raise AssertionError(f"refund identity mismatch: {body!r}")
    if body["status"] != "PENDING" or body["provider"] != "MANUAL":
        raise AssertionError(f"refund status/provider mismatch: {body!r}")
    if body["out_refund_no"] != expected_out_refund_no(refund_id):
        raise AssertionError(f"out_refund_no mismatch: {body!r}")
    if body["provider_refund_id"] is not None or body["completed_at"] is not None:
        raise AssertionError(f"unexpected completed refund fields: {body!r}")


def verify_manual_storage(refund_id: str, order_id: str) -> None:
    row = refund_row(refund_id)
    if row["status"] != "PENDING" or row["provider"] != "MANUAL":
        raise AssertionError(f"stored refund state mismatch: {row!r}")
    if row["out_refund_no"] != expected_out_refund_no(refund_id):
        raise AssertionError(f"stored out_refund_no mismatch: {row!r}")
    if row["raw_payload"] != {"submit": {"mode": "manual"}}:
        raise AssertionError(f"stored refund payload mismatch: {row!r}")
    if row["failure_reason"] is not None:
        raise AssertionError(f"unexpected failure reason: {row!r}")
    if order_status(order_id) != "REFUNDING":
        raise AssertionError("manual submit mutated order state")


def assert_same_error(
    python_base: str,
    go_base: str,
    refund_id: str,
    headers: dict[str, str],
    *,
    status: int,
    detail: str,
    label: str,
) -> None:
    for base, runtime in ((python_base, "FastAPI"), (go_base, "Go")):
        response = expect(
            submit(base, refund_id, headers),
            status,
            f"{runtime} {label}",
        )
        if response.body.get("detail") != detail:
            raise AssertionError(
                f"{runtime} {label}: body={response.body!r}, want={detail!r}"
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
    customer_id = bootstrap["customerUserId"]
    admin_id = bootstrap["adminUserId"]
    player_id = bootstrap["playerUserId"]
    customer_headers = {"X-User-Id": customer_id}
    admin_headers = {"X-Admin-Id": admin_id}
    player_headers = {"X-User-Id": player_id}
    sku_id = bootstrap["games"][0]["skus"][0]["id"]

    go_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-refund-submit",
    )
    go_refund = seed_refund(
        go_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    go_first = expect(
        submit(args.go_base, go_refund, admin_headers),
        200,
        "Go refund submit",
    ).body
    assert_manual_result(go_first, refund_id=go_refund, order_id=go_order["id"])
    verify_manual_storage(go_refund, go_order["id"])

    py_replay = expect(
        submit(args.python_base, go_refund, admin_headers),
        200,
        "FastAPI replays Go refund submit",
    ).body
    if py_replay != go_first:
        raise AssertionError(
            f"cross-runtime refund replay mismatch FastAPI={py_replay!r} Go={go_first!r}"
        )
    verify_manual_storage(go_refund, go_order["id"])
    print("PASS Go submit + FastAPI replay")

    py_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "python-refund-submit",
    )
    py_refund = seed_refund(
        py_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    py_first = expect(
        submit(args.python_base, py_refund, admin_headers),
        200,
        "FastAPI refund submit",
    ).body
    go_replay = expect(
        submit(args.go_base, py_refund, admin_headers),
        200,
        "Go replays FastAPI refund submit",
    ).body
    if go_replay != py_first:
        raise AssertionError(
            f"Go replay mismatch Go={go_replay!r} FastAPI={py_first!r}"
        )
    verify_manual_storage(py_refund, py_order["id"])
    print("PASS FastAPI submit + Go replay")

    # 20-way submit race: stable merchant refund id makes provider submission replay-safe.
    race_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-submit-race",
    )
    race_refund = seed_refund(
        race_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )

    def run_submit(_index: int) -> Response:
        return submit(args.go_base, race_refund, admin_headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        responses = list(executor.map(run_submit, range(20)))
    failures = [response for response in responses if response.status != 200]
    if failures:
        raise AssertionError(f"concurrent refund submit failures: {failures!r}")
    for response in responses:
        assert_manual_result(
            response.body,
            refund_id=race_refund,
            order_id=race_order["id"],
        )
    verify_manual_storage(race_refund, race_order["id"])
    print("PASS 20-way refund submit keeps one stable provider idempotency key")

    # Already processing is a no-op in both runtimes.
    processing_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-processing-noop",
    )
    processing_out = "RFD_PROCESSING_" + uuid.uuid4().hex
    processing_refund = seed_refund(
        processing_order,
        customer_id=customer_id,
        admin_id=admin_id,
        status="PROCESSING",
        out_refund_no=processing_out,
    )
    py_processing = expect(
        submit(args.python_base, processing_refund, admin_headers),
        200,
        "FastAPI processing refund no-op",
    ).body
    go_processing = expect(
        submit(args.go_base, processing_refund, admin_headers),
        200,
        "Go processing refund no-op",
    ).body
    if go_processing != py_processing:
        raise AssertionError(
            f"processing no-op mismatch FastAPI={py_processing!r} Go={go_processing!r}"
        )
    print("PASS PROCESSING refund submit is idempotent no-op")

    wrong_state_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-wrong-order-state",
    )
    wrong_state_refund = seed_refund(
        wrong_state_order,
        customer_id=customer_id,
        admin_id=admin_id,
        order_status="MATCHING",
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        wrong_state_refund,
        admin_headers,
        status=409,
        detail="ORDER_NOT_REFUNDING",
        label="wrong order state",
    )

    unpaid_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-no-payment",
        pay=False,
    )
    no_payment_refund = seed_refund(
        unpaid_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        no_payment_refund,
        admin_headers,
        status=409,
        detail="SUCCESSFUL_PAYMENT_NOT_FOUND",
        label="missing successful payment",
    )

    missing = "00000000-0000-0000-0000-000000000000"
    assert_same_error(
        args.python_base,
        args.go_base,
        missing,
        admin_headers,
        status=404,
        detail="REFUND_NOT_FOUND",
        label="missing refund",
    )

    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        invalid = expect(
            submit(base, "not-a-uuid", admin_headers),
            422,
            f"{runtime} invalid refund id",
        )
        if not invalid.body:
            raise AssertionError(f"{runtime} invalid UUID missing validation body")

        forbidden = expect(
            submit(base, go_refund, player_headers),
            403,
            f"{runtime} non-platform refund submit",
        )
        if forbidden.body.get("detail") != "PLATFORM_REQUIRED":
            raise AssertionError(
                f"{runtime} platform guard mismatch: {forbidden.body!r}"
            )

    print("M4.3 refund submit parity PASS")
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
        print(f"M4.3 refund submit parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
