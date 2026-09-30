#!/usr/bin/env python3
"""Verify M3.4 customer confirmation and settlement interoperability."""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from go_lifecycle_parity import (
    Response,
    call,
    claim,
    create_and_pay,
    dsn,
    expect,
    seed_provider,
    transition_projection,
)


@dataclass(frozen=True)
class WalletState:
    wallet_id: str | None
    available: int
    frozen: int
    version: int


def wallet_state(user_id: str) -> WalletState:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, available_balance, frozen_balance, version
                FROM wallets
                WHERE user_id = %s::uuid
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    if row is None:
        return WalletState(None, 0, 0, 0)
    return WalletState(row[0], row[1], row[2], row[3])


def platform_user_id() -> str:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text
                FROM users
                WHERE role = 'PLATFORM'
                ORDER BY created_at, id
                LIMIT 1
                """
            )
            row = cursor.fetchone()
    if row is None:
        raise AssertionError("platform account missing from seed")
    return row[0]


def prepare_finished(
    go_base: str,
    python_base: str,
    customer_headers: dict[str, str],
    player_headers: dict[str, str],
    sku_id: str,
    remark: str,
) -> dict[str, Any]:
    paid = create_and_pay(
        go_base,
        python_base,
        customer_headers,
        sku_id,
        remark,
    )
    claim(go_base, player_headers, paid, f"claim {remark}")
    expect(
        call(
            go_base,
            f"/api/v1/player/orders/{paid['id']}/start",
            method="POST",
            headers=player_headers,
        ),
        200,
        f"start {remark}",
    )
    return expect(
        call(
            go_base,
            f"/api/v1/player/orders/{paid['id']}/finish",
            method="POST",
            headers=player_headers,
        ),
        200,
        f"finish {remark}",
    ).body


def assert_wallet_delta(
    before: WalletState,
    after: WalletState,
    amount: int,
    label: str,
) -> None:
    if after.wallet_id is None:
        raise AssertionError(f"{label}: wallet was not created")
    if after.available - before.available != amount:
        raise AssertionError(
            f"{label}: balance delta={after.available - before.available}, "
            f"expected={amount}"
        )
    if after.frozen != before.frozen:
        raise AssertionError(
            f"{label}: frozen balance changed {before.frozen} -> {after.frozen}"
        )
    if after.version != before.version + 1:
        raise AssertionError(
            f"{label}: wallet version {before.version} -> {after.version}, expected +1"
        )


def verify_money_and_evidence(
    order: dict[str, Any],
    *,
    provider_user_id: str,
    provider_player_id: str,
    platform_user: str,
    finished_version: int,
) -> None:
    order_id = order["id"]
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    version,
                    completed_at IS NOT NULL,
                    settled_at IS NOT NULL
                FROM orders
                WHERE id = %s::uuid
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            expected = ("SETTLED", finished_version + 2, True, True)
            if row != expected:
                raise AssertionError(
                    f"settled order mismatch got={row!r} want={expected!r}"
                )

            cursor.execute(
                """
                SELECT
                    player_id::text,
                    gross_amount,
                    player_amount,
                    platform_fee,
                    status,
                    idempotency_key,
                    completed_at IS NOT NULL
                FROM settlements
                WHERE order_id = %s::uuid
                """,
                (order_id,),
            )
            settlements = cursor.fetchall()
            expected_settlement = [
                (
                    provider_player_id,
                    order["total_amount"],
                    order["player_amount"],
                    order["platform_fee"],
                    "COMPLETED",
                    f"order:{order_id}:settlement",
                    True,
                )
            ]
            if settlements != expected_settlement:
                raise AssertionError(
                    "settlement mismatch "
                    f"got={settlements!r} want={expected_settlement!r}"
                )

            cursor.execute(
                """
                SELECT
                    w.user_id::text,
                    l.entry_type,
                    l.amount,
                    l.balance_after
                FROM ledger_entries l
                JOIN wallets w ON w.id = l.account_id
                WHERE l.biz_type = 'ORDER_SETTLEMENT'
                  AND l.biz_id = %s
                ORDER BY l.entry_type
                """,
                (order_id,),
            )
            ledgers = cursor.fetchall()
            if len(ledgers) != 2:
                raise AssertionError(
                    f"expected two settlement ledger entries, got {ledgers!r}"
                )
            ledger_by_type = {row[1]: row for row in ledgers}
            provider = ledger_by_type.get("PROVIDER_INCOME")
            platform = ledger_by_type.get("PLATFORM_FEE")
            if provider is None or provider[0] != provider_user_id:
                raise AssertionError(f"provider ledger mismatch: {provider!r}")
            if provider[2] != order["player_amount"]:
                raise AssertionError(f"provider ledger amount mismatch: {provider!r}")
            if platform is None or platform[0] != platform_user:
                raise AssertionError(f"platform ledger mismatch: {platform!r}")
            if platform[2] != order["platform_fee"]:
                raise AssertionError(f"platform ledger amount mismatch: {platform!r}")

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
                    'USER_CONFIRMED_FINISH',
                    'SETTLEMENT_COMPLETED'
                  )
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            events = cursor.fetchall()
            if len(events) != 2:
                raise AssertionError(f"expected two settlement events, got {events!r}")
            confirmed, settled = events
            if confirmed[:5] != (
                "USER_CONFIRMED_FINISH",
                "FINISH_REQUESTED",
                "COMPLETED",
                "USER",
                order["user_id"],
            ):
                raise AssertionError(f"confirmation evidence mismatch: {confirmed!r}")
            if confirmed[5] != {}:
                raise AssertionError(f"confirmation payload mismatch: {confirmed[5]!r}")
            if settled[:5] != (
                "SETTLEMENT_COMPLETED",
                "COMPLETED",
                "SETTLED",
                "SYSTEM",
                None,
            ):
                raise AssertionError(f"settlement evidence mismatch: {settled!r}")
            if settled[5] != {
                "playerAmount": order["player_amount"],
                "platformFee": order["platform_fee"],
            }:
                raise AssertionError(f"settlement payload mismatch: {settled[5]!r}")

            cursor.execute(
                """
                SELECT event_type, payload_json
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type IN (
                    'USER_CONFIRMED_FINISH',
                    'SETTLEMENT_COMPLETED'
                  )
                ORDER BY created_at, id
                """,
                (order_id,),
            )
            outbox = cursor.fetchall()
            if len(outbox) != 2:
                raise AssertionError(
                    f"expected two settlement outbox rows, got {outbox!r}"
                )
            outbox_map = {event_type: payload for event_type, payload in outbox}
            if outbox_map["USER_CONFIRMED_FINISH"] != {
                "orderId": order_id,
                "status": "COMPLETED",
            }:
                raise AssertionError(
                    "confirmation outbox mismatch: "
                    f"{outbox_map['USER_CONFIRMED_FINISH']!r}"
                )
            if outbox_map["SETTLEMENT_COMPLETED"] != {
                "orderId": order_id,
                "status": "SETTLED",
                "playerAmount": order["player_amount"],
                "platformFee": order["platform_fee"],
            }:
                raise AssertionError(
                    "settlement outbox mismatch: "
                    f"{outbox_map['SETTLEMENT_COMPLETED']!r}"
                )


def confirm(
    base: str,
    order_id: str,
    customer_headers: dict[str, str],
    label: str,
) -> dict[str, Any]:
    return expect(
        call(
            base,
            f"/api/v1/orders/{order_id}/confirm",
            method="POST",
            headers=customer_headers,
        ),
        200,
        label,
    ).body


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
            f"{label}: FastAPI={reference.body!r} Go={target.body!r}"
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
    customer_headers = {"X-User-Id": customer_id}
    sku_id = bootstrap["games"][0]["skus"][0]["id"]
    platform_id = platform_user_id()

    provider_user_id, provider_player_id = seed_provider(
        sku_id,
        "Settlement Provider",
    )
    player_headers = {"X-User-Id": provider_user_id}

    finished = prepare_finished(
        args.go_base,
        args.python_base,
        customer_headers,
        player_headers,
        sku_id,
        "go-settlement-happy",
    )
    provider_before = wallet_state(provider_user_id)
    platform_before = wallet_state(platform_id)

    settled = confirm(
        args.go_base,
        finished["id"],
        customer_headers,
        "Go confirms and settles",
    )
    if settled["status"] != "SETTLED" or settled["version"] != finished["version"] + 2:
        raise AssertionError(f"unexpected Go settlement projection: {settled!r}")

    python_read = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{settled['id']}",
            headers=customer_headers,
        ),
        200,
        "FastAPI reads Go settlement",
    ).body
    if transition_projection(python_read) != transition_projection(settled):
        raise AssertionError(
            "FastAPI did not observe Go settlement "
            f"FastAPI={transition_projection(python_read)!r} "
            f"Go={transition_projection(settled)!r}"
        )

    provider_after = wallet_state(provider_user_id)
    platform_after = wallet_state(platform_id)
    assert_wallet_delta(
        provider_before,
        provider_after,
        settled["player_amount"],
        "provider wallet",
    )
    assert_wallet_delta(
        platform_before,
        platform_after,
        settled["platform_fee"],
        "platform wallet",
    )
    verify_money_and_evidence(
        settled,
        provider_user_id=provider_user_id,
        provider_player_id=provider_player_id,
        platform_user=platform_id,
        finished_version=finished["version"],
    )
    print("PASS Go settlement value flow and durable evidence")

    # Cross-runtime idempotency: both runtimes may replay confirmation after SETTLED.
    py_replay = confirm(
        args.python_base,
        settled["id"],
        customer_headers,
        "FastAPI replays Go settlement",
    )
    go_replay = confirm(
        args.go_base,
        settled["id"],
        customer_headers,
        "Go replays settled order",
    )
    if transition_projection(py_replay) != transition_projection(settled):
        raise AssertionError(f"FastAPI replay changed order: {py_replay!r}")
    if transition_projection(go_replay) != transition_projection(settled):
        raise AssertionError(f"Go replay changed order: {go_replay!r}")
    if wallet_state(provider_user_id) != provider_after:
        raise AssertionError("provider wallet changed on replay")
    if wallet_state(platform_id) != platform_after:
        raise AssertionError("platform wallet changed on replay")
    verify_money_and_evidence(
        settled,
        provider_user_id=provider_user_id,
        provider_player_id=provider_player_id,
        platform_user=platform_id,
        finished_version=finished["version"],
    )
    print("PASS cross-runtime settlement replay is idempotent")

    # Concurrent double/multi-click confirmation must settle exactly once.
    concurrent_finished = prepare_finished(
        args.go_base,
        args.python_base,
        customer_headers,
        player_headers,
        sku_id,
        "go-settlement-concurrent",
    )
    provider_concurrent_before = wallet_state(provider_user_id)
    platform_concurrent_before = wallet_state(platform_id)

    def run_confirm(_index: int) -> Response:
        return call(
            args.go_base,
            f"/api/v1/orders/{concurrent_finished['id']}/confirm",
            method="POST",
            headers=customer_headers,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        responses = list(executor.map(run_confirm, range(20)))
    failures = [
        response
        for response in responses
        if response.status != 200 or response.body.get("status") != "SETTLED"
    ]
    if failures:
        raise AssertionError(f"concurrent confirm failures: {failures!r}")

    provider_concurrent_after = wallet_state(provider_user_id)
    platform_concurrent_after = wallet_state(platform_id)
    assert_wallet_delta(
        provider_concurrent_before,
        provider_concurrent_after,
        concurrent_finished["player_amount"],
        "concurrent provider wallet",
    )
    assert_wallet_delta(
        platform_concurrent_before,
        platform_concurrent_after,
        concurrent_finished["platform_fee"],
        "concurrent platform wallet",
    )
    concurrent_settled = responses[0].body
    verify_money_and_evidence(
        concurrent_settled,
        provider_user_id=provider_user_id,
        provider_player_id=provider_player_id,
        platform_user=platform_id,
        finished_version=concurrent_finished["version"],
    )
    print("PASS 20-way customer confirm settles exactly once")

    # Wrong owner is rejected before idempotency/state handling.
    wrong_owner_finished = prepare_finished(
        args.go_base,
        args.python_base,
        customer_headers,
        player_headers,
        sku_id,
        "settlement-wrong-owner",
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{wrong_owner_finished['id']}/confirm",
        headers=player_headers,
        expected_status=403,
        label="wrong settlement owner",
    )

    # Premature confirmation has exact error parity and no money mutation.
    premature = create_and_pay(
        args.go_base,
        args.python_base,
        customer_headers,
        sku_id,
        "settlement-premature",
    )
    claim(args.go_base, player_headers, premature, "claim premature settlement")
    expect(
        call(
            args.go_base,
            f"/api/v1/player/orders/{premature['id']}/start",
            method="POST",
            headers=player_headers,
        ),
        200,
        "start premature settlement",
    )
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{premature['id']}/confirm",
        headers=customer_headers,
        expected_status=409,
        label="premature settlement",
    )

    missing = "00000000-0000-0000-0000-000000000000"
    assert_same_error(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{missing}/confirm",
        headers=customer_headers,
        expected_status=404,
        label="missing settlement order",
    )
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        response = expect(
            call(
                base,
                "/api/v1/orders/not-a-uuid/confirm",
                method="POST",
                headers=customer_headers,
            ),
            422,
            f"{runtime} invalid settlement order id",
        )
        if not response.body:
            raise AssertionError(f"{runtime} invalid UUID missing validation body")

    print("M3.4 customer settlement parity PASS")
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
        print(f"M3.4 customer settlement parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
