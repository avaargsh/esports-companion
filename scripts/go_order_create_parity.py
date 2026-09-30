#!/usr/bin/env python3
"""Verify M3.1 order-create interoperability and durable evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass
class Response:
    status: int
    body: Any


def call(
    base: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return Response(response.status, json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return Response(exc.code, json.loads(raw) if raw else None)


def expect(response: Response, status: int, label: str) -> Response:
    if response.status != status:
        raise AssertionError(
            f"{label}: expected {status}, got {response.status} body={response.body!r}"
        )
    return response


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, str) and value.endswith("+00:00"):
        return value[:-6] + "Z"
    return value


def get_same(
    python_base: str,
    go_base: str,
    path: str,
    *,
    headers: dict[str, str],
) -> Response:
    reference = expect(call(python_base, path, headers=headers), 200, f"FastAPI {path}")
    target = expect(call(go_base, path, headers=headers), 200, f"Go {path}")
    if normalize(reference.body) != normalize(target.body):
        raise AssertionError(
            f"{path}: body mismatch\n"
            f"FastAPI={json.dumps(normalize(reference.body), ensure_ascii=False, sort_keys=True)}\n"
            f"Go={json.dumps(normalize(target.body), ensure_ascii=False, sort_keys=True)}"
        )
    return target


def expect_same_error(
    python_base: str,
    go_base: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str],
    status: int,
    detail: str | None = None,
    label: str,
) -> None:
    responses = {
        "FastAPI": call(
            python_base,
            "/api/v1/orders",
            method="POST",
            headers=headers,
            body=body,
        ),
        "Go": call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=headers,
            body=body,
        ),
    }
    for runtime, response in responses.items():
        expect(response, status, f"{runtime} {label}")
        if detail is not None and response.body.get("detail") != detail:
            raise AssertionError(
                f"{runtime} {label}: expected detail {detail!r}, got {response.body!r}"
            )


def economics(order: dict[str, Any]) -> dict[str, Any]:
    return {
        key: order[key]
        for key in (
            "game_id",
            "sku_id",
            "status",
            "quantity",
            "unit_price",
            "total_amount",
            "player_amount",
            "platform_fee",
            "version",
        )
    }


def verify_durable_evidence(order_id: str, designated_player_id: str | None) -> None:
    dsn = os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://",
        "postgresql://",
        1,
    )
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_type, from_status, to_status, actor_type, actor_id,
                       payload_json
                FROM order_events
                WHERE order_id = %s::uuid
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            events = cursor.fetchall()
            if len(events) != 1:
                raise AssertionError(
                    f"expected exactly one ORDER_CREATED event, got {len(events)}"
                )
            event_type, from_status, to_status, actor_type, actor_id, payload = events[0]
            if (
                event_type != "ORDER_CREATED"
                or from_status is not None
                or to_status != "WAITING_PAYMENT"
                or actor_type != "USER"
                or not actor_id
            ):
                raise AssertionError(f"unexpected order event: {events[0]!r}")
            if payload.get("designatedPlayerId") != designated_player_id:
                raise AssertionError(f"unexpected order event payload: {payload!r}")

            cursor.execute(
                """
                SELECT event_type, payload_json, status
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type = 'ORDER_CREATED'
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            outbox = cursor.fetchall()
            if len(outbox) != 1:
                raise AssertionError(
                    f"expected exactly one ORDER_CREATED outbox row, got {len(outbox)}"
                )
            event_type, payload, status = outbox[0]
            if event_type != "ORDER_CREATED" or status != "PENDING":
                raise AssertionError(f"unexpected outbox row: {outbox[0]!r}")
            if payload.get("orderId") != order_id:
                raise AssertionError(f"outbox orderId mismatch: {payload!r}")
            if payload.get("status") != "WAITING_PAYMENT":
                raise AssertionError(f"outbox status mismatch: {payload!r}")
            if payload.get("designatedPlayerId") != designated_player_id:
                raise AssertionError(f"outbox designated player mismatch: {payload!r}")


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
    player_headers = {"X-User-Id": bootstrap["playerUserId"]}
    game = bootstrap["games"][0]
    sku = game["skus"][0]

    pooled_body = {
        "sku_id": sku["id"],
        "quantity": 2,
        "remark": "go-order-create-parity",
    }
    go_created = expect(
        call(
            args.go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body=pooled_body,
        ),
        201,
        "Go creates pooled order",
    ).body
    python_reference = expect(
        call(
            args.python_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body=pooled_body,
        ),
        201,
        "FastAPI creates equivalent pooled order",
    ).body
    if economics(go_created) != economics(python_reference):
        raise AssertionError(
            "pooled order economics mismatch "
            f"FastAPI={economics(python_reference)!r} Go={economics(go_created)!r}"
        )
    if not go_created["order_no"].startswith("ORD_"):
        raise AssertionError(f"unexpected Go order number: {go_created['order_no']!r}")

    pooled_id = go_created["id"]
    get_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{pooled_id}",
        headers=customer_headers,
    )
    events = get_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{pooled_id}/events",
        headers=customer_headers,
    ).body
    if [item["event_type"] for item in events] != ["ORDER_CREATED"]:
        raise AssertionError(f"unexpected create event stream: {events!r}")
    verify_durable_evidence(pooled_id, None)
    print("PASS pooled order create + durable evidence")

    public_player = expect(
        call(
            args.python_base,
            f"/api/v1/players/{bootstrap['playerProfileId']}",
        ),
        200,
        "public player",
    ).body
    if not public_player["offerings"]:
        raise AssertionError("seeded provider has no offering")
    offering = public_player["offerings"][0]

    designated_body = {
        "offering_id": offering["id"],
        "quantity": 1,
        "remark": "go-designated-create-parity",
    }
    designated = expect(
        call(
            args.go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body=designated_body,
        ),
        201,
        "Go creates designated order",
    ).body
    designated_id = designated["id"]
    if designated["designated_player_id"] != bootstrap["playerProfileId"]:
        raise AssertionError(f"designated provider mismatch: {designated!r}")
    detail = get_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{designated_id}",
        headers=customer_headers,
    ).body
    if detail["service_player"]["binding"] != "DESIGNATED":
        raise AssertionError(f"designated projection missing: {detail!r}")
    verify_durable_evidence(designated_id, bootstrap["playerProfileId"])
    print("PASS designated order create + durable evidence")

    missing = "00000000-0000-0000-0000-000000000000"
    expect_same_error(
        args.python_base,
        args.go_base,
        {},
        headers=customer_headers,
        status=409,
        detail="ORDER_REQUIRES_EXACTLY_ONE_SKU_OR_OFFERING",
        label="requires exactly one source",
    )
    expect_same_error(
        args.python_base,
        args.go_base,
        {"sku_id": sku["id"], "offering_id": offering["id"]},
        headers=customer_headers,
        status=409,
        detail="ORDER_REQUIRES_EXACTLY_ONE_SKU_OR_OFFERING",
        label="rejects both SKU and offering",
    )
    expect_same_error(
        args.python_base,
        args.go_base,
        {"sku_id": missing},
        headers=customer_headers,
        status=409,
        detail="SKU_NOT_AVAILABLE",
        label="rejects missing SKU",
    )
    expect_same_error(
        args.python_base,
        args.go_base,
        {"offering_id": missing},
        headers=customer_headers,
        status=409,
        detail="OFFERING_NOT_AVAILABLE",
        label="rejects missing offering",
    )
    expect_same_error(
        args.python_base,
        args.go_base,
        {"offering_id": offering["id"]},
        headers=player_headers,
        status=409,
        detail="CANNOT_ORDER_OWN_OFFERING",
        label="rejects own offering",
    )

    for body, label in (
        ({"sku_id": "not-a-uuid"}, "invalid SKU UUID"),
        ({"sku_id": sku["id"], "quantity": 0}, "quantity below minimum"),
        ({"sku_id": sku["id"], "quantity": 11}, "quantity above maximum"),
        ({"sku_id": sku["id"], "quantity": None}, "null quantity"),
        ({"sku_id": sku["id"], "remark": None}, "null remark"),
        ({"sku_id": sku["id"], "remark": "x" * 501}, "remark too long"),
    ):
        expect_same_error(
            args.python_base,
            args.go_base,
            body,
            headers=customer_headers,
            status=422,
            label=label,
        )

    print("M3.1 order create parity PASS")
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
        print(f"M3.1 order create parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
