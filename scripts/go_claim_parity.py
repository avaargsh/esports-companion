#!/usr/bin/env python3
"""Verify M3.2 atomic claim parity and one-winner concurrency."""

from __future__ import annotations

import argparse
import concurrent.futures
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
        with urllib.request.urlopen(request, timeout=20) as response:
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
    return os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://",
        "postgresql://",
        1,
    )


def create_and_pay(
    go_base: str,
    python_base: str,
    customer_headers: dict[str, str],
    sku_id: str,
    label: str,
) -> dict[str, Any]:
    order = expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": label,
            },
        ),
        201,
        f"{label} create",
    ).body
    return expect(
        call(
            python_base,
            f"/api/v1/orders/{order['id']}/mock-pay",
            method="POST",
            headers={
                **customer_headers,
                "Idempotency-Key": f"{label}-{uuid.uuid4().hex}",
            },
        ),
        200,
        f"{label} payment",
    ).body


def claim_projection(order: dict[str, Any]) -> dict[str, Any]:
    return {
        key: order[key]
        for key in (
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


def seed_concurrent_players(sku_id: str, count: int) -> list[tuple[str, str]]:
    players: list[tuple[str, str]] = []
    suffix = uuid.uuid4().hex[:10]
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            for index in range(count):
                user_id = str(uuid.uuid4())
                player_id = str(uuid.uuid4())
                offering_id = str(uuid.uuid4())
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
                    (user_id, f"go-claim-{suffix}-{index}"),
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
                    (player_id, user_id, f"Claim Player {index}"),
                )
                cursor.execute(
                    """
                    INSERT INTO provider_offerings (
                        id, player_id, sku_id, price_override,
                        description, status, created_at, updated_at
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, NULL,
                        'atomic claim parity', 'ACTIVE', now(), now()
                    )
                    """,
                    (offering_id, player_id, sku_id),
                )
                players.append((user_id, player_id))
        connection.commit()
    return players


def verify_claim_evidence(
    order_id: str,
    expected_version: int,
    player_by_user: dict[str, str],
    winner_user_id: str,
) -> None:
    winner_player_id = player_by_user[winner_user_id]
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, version
                FROM orders
                WHERE id = %s::uuid
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            if row != ("ACCEPTED", expected_version + 1):
                raise AssertionError(f"unexpected claimed order state: {row!r}")

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
            if assignments != [(winner_player_id, "PLAYER")]:
                raise AssertionError(
                    f"expected exactly winner active assignment, got {assignments!r}"
                )

            cursor.execute(
                """
                SELECT event_type, from_status, to_status, actor_type, actor_id
                FROM order_events
                WHERE order_id = %s::uuid
                  AND event_type = 'PLAYER_CLAIMED'
                """,
                (order_id,),
            )
            events = cursor.fetchall()
            if events != [
                (
                    "PLAYER_CLAIMED",
                    "MATCHING",
                    "ACCEPTED",
                    "PLAYER",
                    winner_player_id,
                )
            ]:
                raise AssertionError(f"unexpected claim events: {events!r}")

            cursor.execute(
                """
                SELECT payload_json, status
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type = 'PLAYER_CLAIMED'
                """,
                (order_id,),
            )
            outbox = cursor.fetchall()
            if len(outbox) != 1:
                raise AssertionError(
                    f"expected one PLAYER_CLAIMED outbox event, got {len(outbox)}"
                )
            payload, status = outbox[0]
            if payload.get("orderId") != order_id or payload.get("status") != "ACCEPTED":
                raise AssertionError(f"unexpected claim outbox payload: {payload!r}")
            if status not in {"PENDING", "PUBLISHED"}:
                raise AssertionError(f"unexpected claim outbox status: {status!r}")


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
    sku_id = bootstrap["games"][0]["skus"][0]["id"]

    # Single-claim compatibility: compare equivalent FastAPI and Go transitions.
    go_paid = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "go-single-claim",
    )
    go_claim = expect(
        call(
            args.go_base,
            f"/api/v1/player/orders/{go_paid['id']}/claim",
            method="POST",
            headers=player_headers,
            body={"expected_version": go_paid["version"]},
        ),
        200,
        "Go single claim",
    ).body

    py_paid = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "python-single-claim",
    )
    py_claim = expect(
        call(
            args.python_base,
            f"/api/v1/player/orders/{py_paid['id']}/claim",
            method="POST",
            headers=player_headers,
            body={"expected_version": py_paid["version"]},
        ),
        200,
        "FastAPI single claim",
    ).body
    if claim_projection(go_claim) != claim_projection(py_claim):
        raise AssertionError(
            "claim projection mismatch "
            f"FastAPI={claim_projection(py_claim)!r} Go={claim_projection(go_claim)!r}"
        )

    detail = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{go_paid['id']}",
            headers=customer_headers,
        ),
        200,
        "FastAPI reads Go claim",
    ).body
    if detail["status"] != "ACCEPTED":
        raise AssertionError(f"FastAPI did not observe Go claim: {detail!r}")
    if detail["service_player"]["binding"] != "ASSIGNED":
        raise AssertionError(f"FastAPI assigned-player projection missing: {detail!r}")
    print("PASS single claim cross-runtime compatibility")

    # Stable conflict/error contracts.
    for base, runtime, paid in (
        (args.go_base, "Go", go_paid),
        (args.python_base, "FastAPI", py_paid),
    ):
        repeat = expect(
            call(
                base,
                f"/api/v1/player/orders/{paid['id']}/claim",
                method="POST",
                headers=player_headers,
                body={"expected_version": paid["version"]},
            ),
            409,
            f"{runtime} repeat claim",
        )
        if repeat.body.get("detail") != "ORDER_ALREADY_ACCEPTED":
            raise AssertionError(f"{runtime} repeat claim detail mismatch: {repeat.body!r}")

    missing = "00000000-0000-0000-0000-000000000000"
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        missing_resp = expect(
            call(
                base,
                f"/api/v1/player/orders/{missing}/claim",
                method="POST",
                headers=player_headers,
                body={"expected_version": 0},
            ),
            404,
            f"{runtime} missing order",
        )
        if missing_resp.body.get("detail") != "ORDER_NOT_FOUND":
            raise AssertionError(f"{runtime} missing-order detail mismatch")

        customer_denied = expect(
            call(
                base,
                f"/api/v1/player/orders/{go_paid['id']}/claim",
                method="POST",
                headers=customer_headers,
                body={"expected_version": go_paid["version"]},
            ),
            403,
            f"{runtime} non-player denied",
        )
        if customer_denied.body.get("detail") != "PLAYER_REQUIRED":
            raise AssertionError(f"{runtime} non-player denial mismatch")

        for body, label in (
            ({}, "missing expected_version"),
            ({"expected_version": None}, "null expected_version"),
            ({"expected_version": -1}, "negative expected_version"),
        ):
            response = expect(
                call(
                    base,
                    f"/api/v1/player/orders/{go_paid['id']}/claim",
                    method="POST",
                    headers=player_headers,
                    body=body,
                ),
                422,
                f"{runtime} {label}",
            )
            if not response.body:
                raise AssertionError(f"{runtime} {label}: missing validation body")

    # A player cannot claim an order they created themselves.
    own_paid = create_and_pay(
        args.go_base,
        args.python_base,
        player_headers,
        sku_id,
        "go-own-claim",
    )
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        response = expect(
            call(
                base,
                f"/api/v1/player/orders/{own_paid['id']}/claim",
                method="POST",
                headers=player_headers,
                body={"expected_version": own_paid["version"]},
            ),
            409,
            f"{runtime} own-order claim",
        )
        if response.body.get("detail") != "CANNOT_CLAIM_OWN_ORDER":
            raise AssertionError(f"{runtime} own-order detail mismatch: {response.body!r}")

    # 100 distinct eligible providers race for one order; PostgreSQL CAS must
    # permit exactly one durable winner.
    race_paid = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "go-100-way-claim",
    )
    players = seed_concurrent_players(sku_id, 100)
    player_by_user = dict(players)

    def run_claim(item: tuple[str, str]) -> tuple[str, Response]:
        user_id, _player_id = item
        response = call(
            args.go_base,
            f"/api/v1/player/orders/{race_paid['id']}/claim",
            method="POST",
            headers={"X-User-Id": user_id},
            body={"expected_version": race_paid["version"]},
        )
        return user_id, response

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(run_claim, players))

    winners = [
        (user_id, response)
        for user_id, response in results
        if response.status == 200
    ]
    conflicts = [
        response
        for _user_id, response in results
        if response.status == 409
        and response.body.get("detail") == "ORDER_ALREADY_ACCEPTED"
    ]
    unexpected = [
        (user_id, response.status, response.body)
        for user_id, response in results
        if response.status != 200
        and not (
            response.status == 409
            and response.body.get("detail") == "ORDER_ALREADY_ACCEPTED"
        )
    ]

    if len(winners) != 1 or len(conflicts) != 99 or unexpected:
        raise AssertionError(
            "100-way claim failed "
            f"winners={len(winners)} conflicts={len(conflicts)} unexpected={unexpected!r}"
        )

    winner_user_id, winner_response = winners[0]
    if winner_response.body["status"] != "ACCEPTED":
        raise AssertionError(f"winner response not ACCEPTED: {winner_response.body!r}")
    if winner_response.body["version"] != race_paid["version"] + 1:
        raise AssertionError(f"winner version mismatch: {winner_response.body!r}")

    verify_claim_evidence(
        race_paid["id"],
        race_paid["version"],
        player_by_user,
        winner_user_id,
    )
    print("PASS 100-way atomic claim: 1 winner / 99 conflicts")
    print("M3.2 atomic claim parity PASS")
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
        print(f"M3.2 atomic claim parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
