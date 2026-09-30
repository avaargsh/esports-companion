#!/usr/bin/env python3
"""Verify M3.3 provider lifecycle interoperability between FastAPI and Go."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
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
        with urllib.request.urlopen(request, timeout=10) as response:
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


def dsn() -> str:
    value = os.environ["DATABASE_URL"]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def seed_provider(sku_id: str, label: str) -> tuple[str, str]:
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
                (user_id, f"{label}-{suffix}"),
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
                (player_id, user_id, f"{label} {suffix}"),
            )
            cursor.execute(
                """
                INSERT INTO provider_offerings (
                    id, player_id, sku_id, price_override,
                    description, status, created_at, updated_at
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, NULL,
                    'lifecycle parity', 'ACTIVE', now(), now()
                )
                """,
                (offering_id, player_id, sku_id),
            )
        connection.commit()
    return user_id, player_id


def create_and_pay(
    go_base: str,
    python_base: str,
    customer_headers: dict[str, str],
    sku_id: str,
    remark: str,
) -> dict[str, Any]:
    order = expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={"sku_id": sku_id, "quantity": 1, "remark": remark},
        ),
        201,
        f"create {remark}",
    ).body
    return expect(
        call(
            python_base,
            f"/api/v1/orders/{order['id']}/mock-pay",
            method="POST",
            headers={
                **customer_headers,
                "Idempotency-Key": f"{remark}-{uuid.uuid4().hex}",
            },
        ),
        200,
        f"pay {remark}",
    ).body


def claim(
    go_base: str,
    player_headers: dict[str, str],
    paid: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    return expect(
        call(
            go_base,
            f"/api/v1/player/orders/{paid['id']}/claim",
            method="POST",
            headers=player_headers,
            body={"expected_version": paid["version"]},
        ),
        200,
        label,
    ).body


def transition_projection(order: dict[str, Any]) -> dict[str, Any]:
    return {
        key: order[key]
        for key in (
            "status",
            "quantity",
            "unit_price",
            "total_amount",
            "player_amount",
            "platform_fee",
            "version",
        )
    }


def verify_lifecycle_evidence(
    order_id: str,
    player_id: str,
    claim_version: int,
) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    version,
                    service_started_at IS NOT NULL,
                    finish_requested_at IS NOT NULL
                FROM orders
                WHERE id = %s::uuid
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            expected = ("FINISH_REQUESTED", claim_version + 2, True, True)
            if row != expected:
                raise AssertionError(
                    f"unexpected lifecycle state: got={row!r} want={expected!r}"
                )

            cursor.execute(
                """
                SELECT event_type, from_status, to_status, actor_type, actor_id
                FROM order_events
                WHERE order_id = %s::uuid
                  AND event_type IN ('SERVICE_STARTED', 'FINISH_REQUESTED')
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            events = cursor.fetchall()
            expected_events = [
                ("SERVICE_STARTED", "ACCEPTED", "IN_SERVICE", "PLAYER", player_id),
                (
                    "FINISH_REQUESTED",
                    "IN_SERVICE",
                    "FINISH_REQUESTED",
                    "PLAYER",
                    player_id,
                ),
            ]
            if events != expected_events:
                raise AssertionError(
                    f"unexpected lifecycle events: got={events!r} want={expected_events!r}"
                )

            cursor.execute(
                """
                SELECT event_type, payload_json, status
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type IN ('SERVICE_STARTED', 'FINISH_REQUESTED')
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            outbox = cursor.fetchall()
            if len(outbox) != 2:
                raise AssertionError(
                    f"expected two lifecycle outbox events, got {len(outbox)}"
                )
            expected_status = {
                "SERVICE_STARTED": "IN_SERVICE",
                "FINISH_REQUESTED": "FINISH_REQUESTED",
            }
            for event_type, payload, status in outbox:
                if payload.get("orderId") != order_id:
                    raise AssertionError(f"wrong outbox order id: {payload!r}")
                if payload.get("status") != expected_status[event_type]:
                    raise AssertionError(f"wrong outbox transition: {payload!r}")
                if status not in {"PENDING", "PUBLISHED"}:
                    raise AssertionError(f"wrong outbox status: {status!r}")


def assert_same_error(
    python_base: str,
    go_base: str,
    path: str,
    *,
    headers: dict[str, str],
    expected_status: int,
    label: str,
) -> None:
    reference = expect(
        call(python_base, path, method="POST", headers=headers),
        expected_status,
        f"FastAPI {label}",
    )
    target = expect(
        call(go_base, path, method="POST", headers=headers),
        expected_status,
        f"Go {label}",
    )
    if reference.body != target.body:
        raise AssertionError(
            f"{label} body mismatch FastAPI={reference.body!r} Go={target.body!r}"
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
    sku_id = bootstrap["games"][0]["skus"][0]["id"]

    provider_user_id, provider_player_id = seed_provider(sku_id, "Lifecycle Provider")
    other_user_id, _other_player_id = seed_provider(sku_id, "Other Provider")
    player_headers = {"X-User-Id": provider_user_id}
    other_headers = {"X-User-Id": other_user_id}

    paid = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "go-lifecycle-happy",
    )
    claimed = claim(args.go_base, player_headers, paid, "Go lifecycle claim")
    claim_version = claimed["version"]

    started = expect(
        call(
            args.go_base,
            f"/api/v1/player/orders/{paid['id']}/start",
            method="POST",
            headers=player_headers,
        ),
        200,
        "Go start",
    ).body
    if started["status"] != "IN_SERVICE" or started["version"] != claim_version + 1:
        raise AssertionError(f"unexpected Go start projection: {started!r}")

    py_after_start = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{paid['id']}",
            headers=customer_headers,
        ),
        200,
        "FastAPI reads Go start",
    ).body
    if transition_projection(py_after_start) != transition_projection(started):
        raise AssertionError(
            "FastAPI did not observe Go start "
            f"FastAPI={transition_projection(py_after_start)!r} "
            f"Go={transition_projection(started)!r}"
        )

    finished = expect(
        call(
            args.go_base,
            f"/api/v1/player/orders/{paid['id']}/finish",
            method="POST",
            headers=player_headers,
        ),
        200,
        "Go finish",
    ).body
    if (
        finished["status"] != "FINISH_REQUESTED"
        or finished["version"] != claim_version + 2
    ):
        raise AssertionError(f"unexpected Go finish projection: {finished!r}")

    py_after_finish = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{paid['id']}",
            headers=customer_headers,
        ),
        200,
        "FastAPI reads Go finish",
    ).body
    if transition_projection(py_after_finish) != transition_projection(finished):
        raise AssertionError(
            "FastAPI did not observe Go finish "
            f"FastAPI={transition_projection(py_after_finish)!r} "
            f"Go={transition_projection(finished)!r}"
        )

    verify_lifecycle_evidence(paid["id"], provider_player_id, claim_version)
    print("PASS Go lifecycle writes are visible to FastAPI with durable evidence")

    # Equivalent FastAPI lifecycle must expose the same transition projection.
    py_paid = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "python-lifecycle-reference",
    )
    py_claimed = claim(args.go_base, player_headers, py_paid, "Go reference claim")
    py_started = expect(
        call(
            args.python_base,
            f"/api/v1/player/orders/{py_paid['id']}/start",
            method="POST",
            headers=player_headers,
        ),
        200,
        "FastAPI start",
    ).body
    if transition_projection(py_started) != {
        **transition_projection(py_claimed),
        "status": "IN_SERVICE",
        "version": py_claimed["version"] + 1,
    }:
        raise AssertionError(f"unexpected FastAPI start projection: {py_started!r}")

    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/player/orders/{py_paid['id']}/start",
        headers=player_headers,
        expected_status=409,
        label="repeated start",
    )

    py_finished = expect(
        call(
            args.python_base,
            f"/api/v1/player/orders/{py_paid['id']}/finish",
            method="POST",
            headers=player_headers,
        ),
        200,
        "FastAPI finish",
    ).body
    if (
        py_finished["status"] != "FINISH_REQUESTED"
        or py_finished["version"] != py_claimed["version"] + 2
    ):
        raise AssertionError(f"unexpected FastAPI finish projection: {py_finished!r}")

    # Assigned player boundary: an unrelated provider cannot start the order.
    wrong_paid = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "wrong-player-lifecycle",
    )
    claim(args.go_base, player_headers, wrong_paid, "claim for wrong-player test")
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/player/orders/{wrong_paid['id']}/start",
        headers=other_headers,
        expected_status=403,
        label="wrong assigned player",
    )

    # Missing assignment is checked after order existence, matching FastAPI.
    unclaimed = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "missing-assignment-lifecycle",
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/player/orders/{unclaimed['id']}/start",
        headers=player_headers,
        expected_status=409,
        label="missing active assignment",
    )

    # Finish cannot skip start.
    finish_early = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "finish-before-start",
    )
    claim(args.go_base, player_headers, finish_early, "claim finish-before-start")
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/player/orders/{finish_early['id']}/finish",
        headers=player_headers,
        expected_status=409,
        label="finish before start",
    )

    # Missing order and malformed path keep framework contract parity.
    missing = "00000000-0000-0000-0000-000000000000"
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/player/orders/{missing}/start",
        headers=player_headers,
        expected_status=404,
        label="missing lifecycle order",
    )
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        response = expect(
            call(
                base,
                "/api/v1/player/orders/not-a-uuid/start",
                method="POST",
                headers=player_headers,
            ),
            422,
            f"{runtime} invalid lifecycle order id",
        )
        if not response.body:
            raise AssertionError(f"{runtime} invalid UUID missing validation body")

    print("M3.3 provider lifecycle parity PASS")
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
        print(f"M3.3 provider lifecycle parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
