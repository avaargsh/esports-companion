#!/usr/bin/env python3
import json
import os
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class SmokeError(RuntimeError):
    pass


def request(method, path, *, headers=None, payload=None, query=None):
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    body = None
    merged_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=merged_headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:  # nosec B310
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(
            f"{method} {path} -> {exc.code}: {raw}"
        ) from exc
    except URLError as exc:
        raise SmokeError(f"{method} {path} failed: {exc}") from exc


def expect_status(actual, expected, step):
    if actual != expected:
        raise SmokeError(f"{step}: expected HTTP {expected}, got {actual}")


def wait_ready():
    deadline = time.time() + 45
    last_error = None
    while time.time() < deadline:
        try:
            status, body = request("GET", "/readyz")
            if status == 200 and body.get("status") == "ready":
                return body
        except SmokeError as exc:
            last_error = exc
        time.sleep(1)
    raise SmokeError(f"API did not become ready: {last_error}")


def run():
    ready = wait_ready()
    print(f"[smoke] ready: {ready['dependencies']}")

    status, demo = request("GET", "/api/v1/dev/bootstrap")
    expect_status(status, 200, "bootstrap")
    customer_id = demo["customerUserId"]
    player_id = demo["playerUserId"]
    game = demo["games"][0]
    sku = game["skus"][0]

    status, order = request(
        "POST",
        "/api/v1/orders",
        headers={"X-User-Id": customer_id},
        payload={
            "sku_id": sku["id"],
            "quantity": 1,
            "remark": "http-smoke",
        },
    )
    expect_status(status, 201, "create order")
    order_id = order["id"]
    if order["status"] != "WAITING_PAYMENT":
        raise SmokeError(f"create order: unexpected state {order['status']}")
    print(f"[smoke] order created: {order_id}")

    status, matching = request(
        "POST",
        f"/api/v1/orders/{order_id}/mock-pay",
        headers={
            "X-User-Id": customer_id,
            "Idempotency-Key": f"smoke-pay-{uuid.uuid4().hex}",
        },
    )
    expect_status(status, 200, "mock payment")
    if matching["status"] != "MATCHING":
        raise SmokeError(f"mock payment: unexpected state {matching['status']}")

    status, pool = request(
        "GET",
        "/api/v1/player/order-pool",
        headers={"X-User-Id": player_id},
        query={"game_id": game["id"]},
    )
    expect_status(status, 200, "order pool")
    if not any(item["id"] == order_id for item in pool):
        raise SmokeError("order pool: new order not visible")

    status, claimed = request(
        "POST",
        f"/api/v1/player/orders/{order_id}/claim",
        headers={"X-User-Id": player_id},
        payload={"expected_version": matching["version"]},
    )
    expect_status(status, 200, "claim")
    if claimed["status"] != "ACCEPTED":
        raise SmokeError(f"claim: unexpected state {claimed['status']}")

    for action, expected in (
        ("start", "IN_SERVICE"),
        ("finish", "FINISH_REQUESTED"),
    ):
        status, current = request(
            "POST",
            f"/api/v1/player/orders/{order_id}/{action}",
            headers={"X-User-Id": player_id},
        )
        expect_status(status, 200, action)
        if current["status"] != expected:
            raise SmokeError(f"{action}: unexpected state {current['status']}")

    status, settled = request(
        "POST",
        f"/api/v1/orders/{order_id}/confirm",
        headers={"X-User-Id": customer_id},
    )
    expect_status(status, 200, "confirm")
    if settled["status"] != "SETTLED":
        raise SmokeError(f"confirm: unexpected state {settled['status']}")

    status, review = request(
        "POST",
        f"/api/v1/orders/{order_id}/reviews",
        headers={"X-User-Id": customer_id},
        payload={"rating": 5, "content": "HTTP smoke verified"},
    )
    expect_status(status, 201, "review")
    if review["rating"] != 5:
        raise SmokeError("review: rating mismatch")

    status, ledger = request(
        "GET",
        "/api/v1/wallet/ledger",
        headers={"X-User-Id": player_id},
    )
    expect_status(status, 200, "ledger")
    player_amount = settled["player_amount"]
    if not any(
        item["bizId"] == order_id
        and item["entryType"] == "PROVIDER_INCOME"
        and item["amount"] == player_amount
        for item in ledger
    ):
        raise SmokeError("ledger: provider settlement entry missing")

    print(
        json.dumps(
            {
                "status": "PASS",
                "orderId": order_id,
                "finalState": settled["status"],
                "providerIncome": player_amount,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        run()
    except (SmokeError, KeyError, IndexError, TypeError) as exc:
        print(f"[smoke] FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
