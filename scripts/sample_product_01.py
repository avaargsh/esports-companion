#!/usr/bin/env python3
"""Sample Product 01: pooled on-demand service marketplace closed loop."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ScenarioError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request(base_url, method, path, *, headers=None, payload=None, query=None):
    url = f"{base_url.rstrip('/')}{path}"
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
        raise ScenarioError(
            f"{method} {path} -> {exc.code}: {raw}"
        ) from exc
    except URLError as exc:
        raise ScenarioError(f"{method} {path} failed: {exc}") from exc


def expect_status(actual, expected, step):
    if actual != expected:
        raise ScenarioError(f"{step}: expected HTTP {expected}, got {actual}")


def expect_state(payload, expected, step):
    actual = payload.get("status")
    if actual != expected:
        raise ScenarioError(f"{step}: expected state {expected}, got {actual}")


def wait_ready(base_url):
    deadline = time.time() + 45
    last_error = None
    while time.time() < deadline:
        try:
            status, body = request(base_url, "GET", "/readyz")
            if status == 200 and body.get("status") == "ready":
                return body
        except ScenarioError as exc:
            last_error = exc
        time.sleep(1)
    raise ScenarioError(f"API did not become ready: {last_error}")


def login(base_url, code, expected_user_id, required_role=None):
    status, payload = request(
        base_url,
        "POST",
        "/api/v1/auth/wechat/login",
        payload={"code": code},
    )
    expect_status(status, 200, f"login {code}")
    if payload["userId"] != expected_user_id:
        raise ScenarioError(f"login {code}: bootstrap identity mismatch")
    if required_role and required_role not in payload["roles"]:
        raise ScenarioError(f"login {code}: role {required_role} missing")
    return {
        "Authorization": f"Bearer {payload['accessToken']}",
    }


def write_evidence(path, evidence):
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(base_url, evidence_path=None):
    started_at = now_iso()
    steps = []

    def passed(name, **details):
        step = {"name": name, "status": "PASS", **details}
        steps.append(step)
        print(f"[sample-product-01] PASS {name}")
        return step

    ready = wait_ready(base_url)
    passed("ready", dependencies=ready.get("dependencies", {}))

    status, demo = request(base_url, "GET", "/api/v1/dev/bootstrap")
    expect_status(status, 200, "bootstrap")
    customer_id = demo["customerUserId"]
    player_user_id = demo["playerUserId"]
    game = demo["games"][0]
    sku = game["skus"][0]
    passed(
        "catalog selected",
        gameId=game["id"],
        gameName=game["name"],
        skuId=sku["id"],
        skuName=sku["name"],
    )

    customer_headers = login(
        base_url,
        "demo-customer",
        customer_id,
    )
    player_headers = login(
        base_url,
        "demo-player-1",
        player_user_id,
        "PLAYER",
    )
    passed("customer and provider authenticated")

    status, player_profile = request(
        base_url,
        "GET",
        "/api/v1/player/profile",
        headers=player_headers,
    )
    expect_status(status, 200, "provider profile")
    provider_id = player_profile["id"]

    status, wallet_before = request(
        base_url,
        "GET",
        "/api/v1/wallet",
        headers=player_headers,
    )
    expect_status(status, 200, "wallet before")
    opening_balance = wallet_before["availableBalance"]
    passed(
        "provider ready",
        providerId=provider_id,
        openingAvailableBalance=opening_balance,
    )

    status, order = request(
        base_url,
        "POST",
        "/api/v1/orders",
        headers=customer_headers,
        payload={
            "sku_id": sku["id"],
            "quantity": 1,
            "remark": "sample-product-01",
        },
    )
    expect_status(status, 201, "create order")
    expect_state(order, "WAITING_PAYMENT", "create order")
    order_id = order["id"]
    state_path = ["WAITING_PAYMENT"]
    passed(
        "customer created order",
        orderId=order_id,
        totalAmount=order["total_amount"],
    )

    status, paid = request(
        base_url,
        "POST",
        f"/api/v1/orders/{order_id}/mock-pay",
        headers={
            **customer_headers,
            "Idempotency-Key": f"sample-01-pay-{uuid.uuid4().hex}",
        },
    )
    expect_status(status, 200, "mock payment")
    expect_state(paid, "MATCHING", "mock payment")
    state_path.append("MATCHING")
    passed("payment entered matching")

    status, pool = request(
        base_url,
        "GET",
        "/api/v1/player/order-pool",
        headers=player_headers,
        query={"game_id": game["id"]},
    )
    expect_status(status, 200, "order pool")
    if not any(item["id"] == order_id for item in pool):
        raise ScenarioError("order pool: paid order is not visible to provider")
    passed("provider discovered order in pool")

    status, claimed = request(
        base_url,
        "POST",
        f"/api/v1/player/orders/{order_id}/claim",
        headers=player_headers,
        payload={"expected_version": paid["version"]},
    )
    expect_status(status, 200, "claim")
    expect_state(claimed, "ACCEPTED", "claim")
    state_path.append("ACCEPTED")
    passed("provider claimed order")

    for action, expected in (
        ("start", "IN_SERVICE"),
        ("finish", "FINISH_REQUESTED"),
    ):
        status, current = request(
            base_url,
            "POST",
            f"/api/v1/player/orders/{order_id}/{action}",
            headers=player_headers,
        )
        expect_status(status, 200, action)
        expect_state(current, expected, action)
        state_path.append(expected)
        passed(f"provider {action}", orderState=expected)

    status, settled = request(
        base_url,
        "POST",
        f"/api/v1/orders/{order_id}/confirm",
        headers=customer_headers,
    )
    expect_status(status, 200, "customer confirm")
    expect_state(settled, "SETTLED", "customer confirm")
    state_path.append("SETTLED")
    passed(
        "customer confirmed and order settled",
        playerAmount=settled["player_amount"],
        platformFee=settled["platform_fee"],
    )

    review_content = f"sample-product-01 verified {order_id}"
    status, review = request(
        base_url,
        "POST",
        f"/api/v1/orders/{order_id}/reviews",
        headers=customer_headers,
        payload={"rating": 5, "content": review_content},
    )
    expect_status(status, 201, "review")
    if review["rating"] != 5:
        raise ScenarioError("review: rating mismatch")
    passed("customer submitted review", reviewId=review["id"])

    status, wallet_after = request(
        base_url,
        "GET",
        "/api/v1/wallet",
        headers=player_headers,
    )
    expect_status(status, 200, "wallet after")
    closing_balance = wallet_after["availableBalance"]
    expected_income = settled["player_amount"]
    actual_delta = closing_balance - opening_balance
    if actual_delta != expected_income:
        raise ScenarioError(
            "wallet: provider available balance delta "
            f"{actual_delta} != settlement {expected_income}"
        )

    status, ledger = request(
        base_url,
        "GET",
        "/api/v1/wallet/ledger",
        headers=player_headers,
    )
    expect_status(status, 200, "provider ledger")
    ledger_entry = next(
        (
            item
            for item in ledger
            if item["bizId"] == order_id
            and item["entryType"] == "PROVIDER_INCOME"
            and item["amount"] == expected_income
        ),
        None,
    )
    if not ledger_entry:
        raise ScenarioError("ledger: provider settlement entry missing")
    passed(
        "provider income materialized",
        closingAvailableBalance=closing_balance,
        providerIncome=expected_income,
        ledgerEntryId=ledger_entry.get("id"),
    )

    status, public_player = request(
        base_url,
        "GET",
        f"/api/v1/players/{provider_id}",
    )
    expect_status(status, 200, "public provider profile")
    public_review = next(
        (
            item
            for item in public_player.get("reviews", [])
            if item.get("id") == review["id"]
            or item.get("content") == review_content
        ),
        None,
    )
    if not public_review:
        raise ScenarioError("reputation: submitted review is not publicly visible")
    if public_player.get("review_count", 0) < 1:
        raise ScenarioError("reputation: public review_count was not updated")
    passed(
        "review fed back into public reputation",
        publicReviewCount=public_player["review_count"],
        publicRating=public_player["rating"],
    )

    status, events = request(
        base_url,
        "GET",
        f"/api/v1/orders/{order_id}/events",
        headers=customer_headers,
    )
    expect_status(status, 200, "order events")
    event_types = [item["event_type"] for item in events]
    required_events = [
        "ORDER_CREATED",
        "PAYMENT_SUCCESS",
        "ORDER_ENTERED_MATCHING",
        "ORDER_CLAIMED",
        "SERVICE_STARTED",
        "FINISH_REQUESTED",
        "USER_CONFIRMED_FINISH",
        "ORDER_SETTLED",
    ]
    missing_events = [item for item in required_events if item not in event_types]
    if missing_events:
        raise ScenarioError(f"order evidence: missing events {missing_events}")
    passed("order evidence trail complete", eventTypes=event_types)

    evidence = {
        "schemaVersion": 1,
        "scenarioId": "sample-product-01-on-demand-service",
        "scenarioName": "Pooled on-demand service marketplace",
        "status": "PASS",
        "startedAt": started_at,
        "finishedAt": now_iso(),
        "baseUrl": base_url,
        "actors": {
            "customerUserId": customer_id,
            "providerUserId": player_user_id,
            "providerId": provider_id,
        },
        "catalog": {
            "gameId": game["id"],
            "gameName": game["name"],
            "skuId": sku["id"],
            "skuName": sku["name"],
        },
        "order": {
            "id": order_id,
            "statePath": state_path,
            "totalAmount": settled["total_amount"],
            "providerAmount": settled["player_amount"],
            "platformFee": settled["platform_fee"],
        },
        "valueFlow": {
            "openingProviderAvailableBalance": opening_balance,
            "closingProviderAvailableBalance": closing_balance,
            "providerIncomeDelta": actual_delta,
            "ledgerEntryId": ledger_entry.get("id"),
        },
        "reputationFlow": {
            "reviewId": review["id"],
            "rating": review["rating"],
            "publicVisible": True,
            "publicReviewCount": public_player["review_count"],
            "publicRating": public_player["rating"],
        },
        "evidence": {
            "requiredEventTypes": required_events,
            "observedEventTypes": event_types,
        },
        "steps": steps,
    }
    write_evidence(evidence_path, evidence)
    print(json.dumps(evidence, ensure_ascii=False))
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--evidence")
    args = parser.parse_args()
    run(args.base_url.rstrip("/"), args.evidence)


if __name__ == "__main__":
    try:
        main()
    except (ScenarioError, KeyError, IndexError, TypeError) as exc:
        print(f"[sample-product-01] FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
