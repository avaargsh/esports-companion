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


def state_code(item):
    return item.get("statusCode") or item.get("status_code") or item.get("status")


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

    status, customer_login = request(
        "POST",
        "/api/v1/auth/wechat/login",
        payload={"code": "demo-customer"},
    )
    expect_status(status, 200, "customer login")
    if customer_login["userId"] != customer_id:
        raise SmokeError("customer login: bootstrap identity mismatch")
    customer_headers = {
        "Authorization": f"Bearer {customer_login['accessToken']}",
    }

    status, player_login = request(
        "POST",
        "/api/v1/auth/wechat/login",
        payload={"code": "demo-player-1"},
    )
    expect_status(status, 200, "player login")
    if player_login["userId"] != player_id:
        raise SmokeError("player login: bootstrap identity mismatch")
    if "PLAYER" not in player_login["roles"]:
        raise SmokeError("player login: PLAYER role missing")
    player_headers = {
        "Authorization": f"Bearer {player_login['accessToken']}",
    }

    game = demo["games"][0]
    sku = game["skus"][0]

    status, order = request(
        "POST",
        "/api/v1/orders",
        headers=customer_headers,
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
            **customer_headers,
            "Idempotency-Key": f"smoke-pay-{uuid.uuid4().hex}",
        },
    )
    expect_status(status, 200, "mock payment")
    if matching["status"] != "MATCHING":
        raise SmokeError(f"mock payment: unexpected state {matching['status']}")

    status, pool = request(
        "GET",
        "/api/v1/player/order-pool",
        headers=player_headers,
        query={"game_id": game["id"]},
    )
    expect_status(status, 200, "order pool")
    if not any(item["id"] == order_id for item in pool):
        raise SmokeError("order pool: new order not visible")

    status, claimed = request(
        "POST",
        f"/api/v1/player/orders/{order_id}/claim",
        headers=player_headers,
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
            headers=player_headers,
        )
        expect_status(status, 200, action)
        if current["status"] != expected:
            raise SmokeError(f"{action}: unexpected state {current['status']}")

    status, settled = request(
        "POST",
        f"/api/v1/orders/{order_id}/confirm",
        headers=customer_headers,
    )
    expect_status(status, 200, "confirm")
    if settled["status"] != "SETTLED":
        raise SmokeError(f"confirm: unexpected state {settled['status']}")

    status, review = request(
        "POST",
        f"/api/v1/orders/{order_id}/reviews",
        headers=customer_headers,
        payload={"rating": 5, "content": "HTTP smoke verified"},
    )
    expect_status(status, 201, "review")
    if review["rating"] != 5:
        raise SmokeError("review: rating mismatch")

    status, ledger = request(
        "GET",
        "/api/v1/wallet/ledger",
        headers=player_headers,
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

    # Discovery + designated booking: direct booking must bypass the public pool.
    status, public_players = request(
        "GET",
        "/api/v1/players",
        query={"game_id": game["id"], "limit": 10},
    )
    expect_status(status, 200, "player discovery")
    if not public_players:
        raise SmokeError("player discovery: no approved available players")
    selected_player = public_players[0]
    selected_offering = next(
        (
            item
            for item in selected_player["offerings"]
            if item["game_id"] == game["id"]
        ),
        None,
    )
    if not selected_offering:
        raise SmokeError("player discovery: selected player has no active offering for game")

    status, designated = request(
        "POST",
        "/api/v1/orders",
        headers=customer_headers,
        payload={
            "offering_id": selected_offering["id"],
            "quantity": 1,
            "remark": "designated-smoke",
        },
    )
    expect_status(status, 201, "designated create")
    designated_id = designated["id"]
    status, designated_paid = request(
        "POST",
        f"/api/v1/orders/{designated_id}/mock-pay",
        headers={
            **customer_headers,
            "Idempotency-Key": f"designated-pay-{uuid.uuid4().hex}",
        },
    )
    expect_status(status, 200, "designated payment")
    if designated_paid["status"] != "ACCEPTED":
        raise SmokeError(
            f"designated payment: expected ACCEPTED, got {designated_paid['status']}"
        )
    status, pool_after_designated = request(
        "GET",
        "/api/v1/player/order-pool",
        headers=player_headers,
        query={"game_id": game["id"]},
    )
    expect_status(status, 200, "designated pool check")
    if any(item["id"] == designated_id for item in pool_after_designated):
        raise SmokeError("designated booking leaked into public order pool")

    # Admin login is part of the product release slice.
    status, admin_login = request(
        "POST",
        "/api/v1/auth/wechat/login",
        payload={"code": "demo-platform"},
    )
    expect_status(status, 200, "admin login")
    if "PLATFORM" not in admin_login["roles"]:
        raise SmokeError("admin login: PLATFORM role missing")
    admin_headers = {
        "Authorization": f"Bearer {admin_login['accessToken']}",
    }

    # Admin dispute handling: list and resolve a real disputed order.
    status, dispute_order = request(
        "POST",
        "/api/v1/orders",
        headers=customer_headers,
        payload={
            "sku_id": sku["id"],
            "quantity": 1,
            "remark": "admin-dispute-smoke",
        },
    )
    expect_status(status, 201, "dispute order create")
    dispute_order_id = dispute_order["id"]
    status, dispute_matching = request(
        "POST",
        f"/api/v1/orders/{dispute_order_id}/mock-pay",
        headers={
            **customer_headers,
            "Idempotency-Key": f"dispute-pay-{uuid.uuid4().hex}",
        },
    )
    expect_status(status, 200, "dispute order payment")
    status, _ = request(
        "POST",
        f"/api/v1/player/orders/{dispute_order_id}/claim",
        headers=player_headers,
        payload={"expected_version": dispute_matching["version"]},
    )
    expect_status(status, 200, "dispute order claim")
    status, _ = request(
        "POST",
        f"/api/v1/player/orders/{dispute_order_id}/start",
        headers=player_headers,
    )
    expect_status(status, 200, "dispute order start")
    status, dispute = request(
        "POST",
        f"/api/v1/orders/{dispute_order_id}/disputes",
        headers={
            **customer_headers,
            "Idempotency-Key": f"dispute-open-{uuid.uuid4().hex}",
        },
        payload={
            "reason_code": "SERVICE_QUALITY",
            "description": "release checklist smoke",
        },
    )
    expect_status(status, 201, "open dispute")
    status, admin_disputes = request(
        "GET",
        "/api/v1/admin/disputes",
        headers=admin_headers,
    )
    expect_status(status, 200, "admin dispute list")
    if not any(item["id"] == dispute["id"] for item in admin_disputes):
        raise SmokeError("admin dispute list: opened dispute missing")
    status, resolved_dispute = request(
        "POST",
        f"/api/v1/admin/disputes/{dispute['id']}/release",
        headers=admin_headers,
    )
    expect_status(status, 200, "admin dispute release")
    if resolved_dispute["status"] != "RESOLVED":
        raise SmokeError("admin dispute release: dispute not resolved")

    # Withdrawal product slice: request -> Admin list -> reject and approve.
    status, rejected_withdrawal = request(
        "POST",
        "/api/v1/withdrawals",
        headers={
            **player_headers,
            "Idempotency-Key": f"withdraw-reject-{uuid.uuid4().hex}",
        },
        payload={"amount": 500},
    )
    expect_status(status, 201, "withdrawal request for reject")
    status, admin_withdrawals = request(
        "GET",
        "/api/v1/admin/withdrawals",
        headers=admin_headers,
    )
    expect_status(status, 200, "admin withdrawal list")
    if not any(item["id"] == rejected_withdrawal["id"] for item in admin_withdrawals):
        raise SmokeError("admin withdrawal list: requested withdrawal missing")
    status, rejected = request(
        "POST",
        f"/api/v1/admin/withdrawals/{rejected_withdrawal['id']}/reject",
        headers=admin_headers,
        query={"reason": "RELEASE_CHECKLIST_REJECT"},
    )
    expect_status(status, 200, "admin withdrawal reject")
    if state_code(rejected) != "REJECTED":
        raise SmokeError("admin withdrawal reject: unexpected state")

    status, approved_withdrawal = request(
        "POST",
        "/api/v1/withdrawals",
        headers={
            **player_headers,
            "Idempotency-Key": f"withdraw-approve-{uuid.uuid4().hex}",
        },
        payload={"amount": 600},
    )
    expect_status(status, 201, "withdrawal request for approve")
    payout_ref = f"smoke-payout-{uuid.uuid4().hex}"
    status, approved = request(
        "POST",
        f"/api/v1/admin/withdrawals/{approved_withdrawal['id']}/complete",
        headers=admin_headers,
        payload={"provider_txn_id": payout_ref},
    )
    expect_status(status, 200, "admin withdrawal approve")
    if state_code(approved) != "COMPLETED":
        raise SmokeError("admin withdrawal approve: unexpected state")
    status, admin_withdrawals = request(
        "GET",
        "/api/v1/admin/withdrawals",
        headers=admin_headers,
    )
    expect_status(status, 200, "admin withdrawal list after review")
    approved_row = next(
        (
            item
            for item in admin_withdrawals
            if item["id"] == approved_withdrawal["id"]
        ),
        None,
    )
    if not approved_row or approved_row["providerTxnId"] != payout_ref:
        raise SmokeError("admin withdrawal approve: payout reference missing")

    print(
        json.dumps(
            {
                "status": "PASS",
                "orderId": order_id,
                "finalState": settled["status"],
                "providerIncome": player_amount,
                "discovery": "PASS",
                "designatedBooking": "PASS",
                "adminDispute": "PASS",
                "withdrawalReject": "PASS",
                "withdrawalApprove": "PASS",
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
