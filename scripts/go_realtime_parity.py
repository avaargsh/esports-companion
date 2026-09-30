#!/usr/bin/env python3
"""Verify M5.2 authenticated WebSocket realtime parity."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Any

import psycopg
import redis
import websockets

from go_claim_parity import call, dsn, expect


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
                    'realtime parity', 'ACTIVE', now(), now()
                )
                """,
                (offering_id, player_id, sku_id),
            )
        connection.commit()
    return user_id, player_id


def prepare_order(
    go_base: str,
    customer_id: str,
    player_user_id: str,
    sku_id: str,
) -> dict[str, Any]:
    customer_headers = {"X-User-Id": customer_id}
    order = expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": "go-realtime-parity",
            },
        ),
        201,
        "create realtime order",
    ).body
    paid = expect(
        call(
            go_base,
            f"/api/v1/orders/{order['id']}/mock-pay",
            method="POST",
            headers={
                **customer_headers,
                "Idempotency-Key": f"realtime-pay-{uuid.uuid4().hex}",
            },
        ),
        200,
        "pay realtime order",
    ).body
    claimed = expect(
        call(
            go_base,
            f"/api/v1/player/orders/{order['id']}/claim",
            method="POST",
            headers={"X-User-Id": player_user_id},
            body={"expected_version": paid["version"]},
        ),
        200,
        "claim realtime order",
    ).body
    return claimed


def ws_url(base: str, user_id: str) -> str:
    return base.replace("http://", "ws://", 1).rstrip("/") + f"/ws?user_id={user_id}"


async def receive_json(ws: Any, timeout: float = 3.0) -> dict[str, Any]:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def receive_type(
    ws: Any,
    expected_type: str,
    timeout: float = 3.0,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise AssertionError(f"timed out waiting for websocket type={expected_type}")
        payload = await receive_json(ws, remaining)
        if payload.get("type") == expected_type:
            return payload


async def subscription_case(
    base: str,
    user_id: str,
    channels: list[str],
    accepted: list[str],
    rejected: list[str],
    label: str,
) -> None:
    async with websockets.connect(ws_url(base, user_id), open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "subscribe", "channels": channels}))
        response = await receive_type(ws, "subscribed")
        expected = {
            "type": "subscribed",
            "channels": accepted,
            "rejected": rejected,
        }
        if response != expected:
            raise AssertionError(
                f"{label}: subscription={response!r} want={expected!r}"
            )


async def protocol_case(base: str, user_id: str, label: str) -> None:
    async with websockets.connect(ws_url(base, user_id), open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "noop"}))
        response = await receive_type(ws, "error")
        if response != {
            "type": "error",
            "code": "UNSUPPORTED_MESSAGE_TYPE",
        }:
            raise AssertionError(f"{label}: unsupported response={response!r}")

        await ws.send(json.dumps({"type": "subscribe", "channels": "bad"}))
        response = await receive_type(ws, "error")
        if response != {
            "type": "error",
            "code": "CHANNELS_REQUIRED",
        }:
            raise AssertionError(f"{label}: channels response={response!r}")


async def receive_event(
    ws: Any,
    event_id: str,
    timeout: float = 3.0,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise AssertionError(f"timed out waiting for eventId={event_id}")
        payload = await receive_json(ws, remaining)
        if payload.get("eventId") == event_id:
            return payload


async def assert_no_event(ws: Any, event_id: str, timeout: float = 0.6) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return
        try:
            payload = await receive_json(ws, remaining)
        except asyncio.TimeoutError:
            return
        if payload.get("eventId") == event_id:
            raise AssertionError(
                f"unauthorized realtime event delivered: {payload!r}"
            )


async def multi_instance_delivery_case(
    go_base: str,
    go_base_2: str,
    order_id: str,
    customer_id: str,
    player_id: str,
) -> None:
    redis_client = redis.Redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )
    order_channel = f"realtime:order:{order_id}"

    async with (
        websockets.connect(ws_url(go_base, customer_id), open_timeout=5) as customer,
        websockets.connect(ws_url(go_base_2, player_id), open_timeout=5) as player,
    ):
        await customer.send(
            json.dumps({
                "type": "subscribe",
                "channels": [f"order:{order_id}"],
            })
        )
        await player.send(
            json.dumps({
                "type": "subscribe",
                "channels": [f"order:{order_id}"],
            })
        )
        customer_ack = await receive_type(customer, "subscribed")
        player_ack = await receive_type(player, "subscribed")
        if customer_ack["channels"] != [f"order:{order_id}"]:
            raise AssertionError(f"instance-1 customer ack={customer_ack!r}")
        if player_ack["channels"] != [f"order:{order_id}"]:
            raise AssertionError(f"instance-2 player ack={player_ack!r}")

        event_id = "realtime-multi-instance-" + uuid.uuid4().hex
        payload = {
            "type": "order.status_changed",
            "eventId": event_id,
            "eventType": "REALTIME_MULTI_INSTANCE",
            "orderId": order_id,
            "status": "ACCEPTED",
        }
        redis_client.publish(order_channel, json.dumps(payload))

        customer_event = await receive_event(customer, event_id)
        player_event = await receive_event(player, event_id)
        if customer_event != payload:
            raise AssertionError(
                f"instance-1 customer event={customer_event!r}"
            )
        if player_event != payload:
            raise AssertionError(
                f"instance-2 player event={player_event!r}"
            )

        # M5.1 is intentionally at-least-once. Publishing the same durable
        # eventId again must not duplicate delivery on either local socket.
        redis_client.publish(order_channel, json.dumps(payload))
        await assert_no_event(customer, event_id)
        await assert_no_event(player, event_id)

    redis_client.close()


async def dynamic_delivery_case(
    go_base: str,
    order_id: str,
    customer_id: str,
    player_id: str,
    platform_id: str,
) -> None:
    redis_client = redis.Redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )
    order_channel = f"realtime:order:{order_id}"
    user_channel = f"realtime:user:{customer_id}"

    async with (
        websockets.connect(ws_url(go_base, customer_id), open_timeout=5) as customer,
        websockets.connect(ws_url(go_base, player_id), open_timeout=5) as player,
        websockets.connect(ws_url(go_base, platform_id), open_timeout=5) as platform,
    ):
        await customer.send(
            json.dumps({
                "type": "subscribe",
                "channels": [f"order:{order_id}", f"user:{customer_id}"],
            })
        )
        await player.send(
            json.dumps({
                "type": "subscribe",
                "channels": [f"order:{order_id}", f"user:{customer_id}"],
            })
        )
        await platform.send(
            json.dumps({
                "type": "subscribe",
                "channels": [f"order:{order_id}", f"user:{customer_id}"],
            })
        )
        customer_ack = await receive_type(customer, "subscribed")
        player_ack = await receive_type(player, "subscribed")
        platform_ack = await receive_type(platform, "subscribed")

        if customer_ack["channels"] != [
            f"order:{order_id}",
            f"user:{customer_id}",
        ]:
            raise AssertionError(f"customer ack={customer_ack!r}")
        if player_ack["channels"] != [f"order:{order_id}"] or player_ack[
            "rejected"
        ] != [f"user:{customer_id}"]:
            raise AssertionError(f"player ack={player_ack!r}")
        if platform_ack["channels"] != [
            f"order:{order_id}",
            f"user:{customer_id}",
        ]:
            raise AssertionError(f"platform ack={platform_ack!r}")

        first_id = "realtime-before-release-" + uuid.uuid4().hex
        first = {
            "type": "order.status_changed",
            "eventId": first_id,
            "eventType": "REALTIME_PARITY",
            "orderId": order_id,
            "status": "ACCEPTED",
        }
        redis_client.publish(order_channel, json.dumps(first))
        for ws, label in (
            (customer, "customer"),
            (player, "active player"),
            (platform, "platform"),
        ):
            received = await receive_event(ws, first_id)
            if received != first:
                raise AssertionError(f"{label} received={received!r}")

        user_id = "realtime-user-" + uuid.uuid4().hex
        user_message = {
            "type": "order.status_changed",
            "eventId": user_id,
            "eventType": "REALTIME_USER_PARITY",
            "orderId": order_id,
            "status": "ACCEPTED",
        }
        redis_client.publish(user_channel, json.dumps(user_message))
        for ws, label in ((customer, "customer"), (platform, "platform")):
            received = await receive_event(ws, user_id)
            if received != user_message:
                raise AssertionError(f"{label} user message={received!r}")
        await assert_no_event(player, user_id)

        with psycopg.connect(dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE order_assignments
                    SET status = 'RELEASED',
                        released_at = clock_timestamp(),
                        updated_at = clock_timestamp()
                    WHERE order_id = %s::uuid
                      AND status = 'ACTIVE'
                    """,
                    (order_id,),
                )
            connection.commit()

        second_id = "realtime-after-release-" + uuid.uuid4().hex
        second = {
            "type": "order.status_changed",
            "eventId": second_id,
            "eventType": "REALTIME_PARITY_RELEASED",
            "orderId": order_id,
            "status": "MATCHING",
        }
        redis_client.publish(order_channel, json.dumps(second))
        for ws, label in ((customer, "customer"), (platform, "platform")):
            received = await receive_event(ws, second_id)
            if received != second:
                raise AssertionError(f"{label} released message={received!r}")
        await assert_no_event(player, second_id)

    redis_client.close()


async def run(args: argparse.Namespace) -> None:
    bootstrap = expect(
        call(args.python_base, "/api/v1/dev/bootstrap"),
        200,
        "bootstrap",
    ).body
    customer_id = bootstrap["customerUserId"]
    platform_id = bootstrap["adminUserId"]
    sku_id = bootstrap["games"][0]["skus"][0]["id"]
    player_user_id, _player_profile_id = seed_provider(
        sku_id,
        "Realtime Active Player",
    )
    unrelated_user_id, _ = seed_provider(
        sku_id,
        "Realtime Unrelated Player",
    )

    order = prepare_order(
        args.go_base,
        customer_id,
        player_user_id,
        sku_id,
    )
    order_id = order["id"]

    customer_channels = [
        f"user:{customer_id}",
        f"order:{order_id}",
        f"user:{player_user_id}",
        "order:not-a-uuid",
        "unsupported:test",
    ]
    for base, runtime in (
        (args.python_base, "FastAPI"),
        (args.go_base, "Go"),
    ):
        await subscription_case(
            base,
            customer_id,
            customer_channels,
            [f"user:{customer_id}", f"order:{order_id}"],
            [
                f"user:{player_user_id}",
                "order:not-a-uuid",
                "unsupported:test",
            ],
            f"{runtime} customer",
        )
        await subscription_case(
            base,
            player_user_id,
            [f"order:{order_id}", f"user:{customer_id}"],
            [f"order:{order_id}"],
            [f"user:{customer_id}"],
            f"{runtime} active player",
        )
        await subscription_case(
            base,
            unrelated_user_id,
            [f"order:{order_id}"],
            [],
            [f"order:{order_id}"],
            f"{runtime} unrelated player",
        )
        await subscription_case(
            base,
            platform_id,
            [f"order:{order_id}", f"user:{customer_id}"],
            [f"order:{order_id}", f"user:{customer_id}"],
            [],
            f"{runtime} platform",
        )
        await protocol_case(base, customer_id, runtime)

        channels = [f"user:{customer_id}"] * 21
        await subscription_case(
            base,
            customer_id,
            channels,
            channels[:20],
            [],
            f"{runtime} 20-channel cap",
        )

    print("PASS FastAPI/Go WebSocket subscription authorization parity")

    await multi_instance_delivery_case(
        args.go_base,
        args.go_base_2,
        order_id,
        customer_id,
        player_user_id,
    )
    print("PASS multi-instance Redis fanout + eventId dedupe")

    await dynamic_delivery_case(
        args.go_base,
        order_id,
        customer_id,
        player_user_id,
        platform_id,
    )
    print("PASS Go Redis->WebSocket dynamic audience revalidation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    parser.add_argument("--go-base-2", default="http://127.0.0.1:8091")
    args = parser.parse_args()
    asyncio.run(run(args))
    print("M5.2 realtime WebSocket parity PASS")
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
    ) as exc:
        print(f"M5.2 realtime parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
