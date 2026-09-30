#!/usr/bin/env python3
"""Verify M3 order read interoperability between FastAPI and Go."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


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


def assert_same(
    python_base: str,
    go_base: str,
    path: str,
    *,
    headers: dict[str, str],
    compare_body: bool = True,
) -> Response:
    reference = call(python_base, path, headers=headers)
    target = call(go_base, path, headers=headers)
    if reference.status != target.status:
        raise AssertionError(
            f"{path}: status mismatch FastAPI={reference.status} Go={target.status}"
        )
    if compare_body and normalize(reference.body) != normalize(target.body):
        raise AssertionError(
            f"{path}: body mismatch\n"
            f"FastAPI={json.dumps(normalize(reference.body), ensure_ascii=False, sort_keys=True)}\n"
            f"Go={json.dumps(normalize(target.body), ensure_ascii=False, sort_keys=True)}"
        )
    print(f"PASS {path} status={reference.status}")
    return reference


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
    identities = expect(
        call(args.python_base, "/api/v1/dev/demo-identities"),
        200,
        "demo identities",
    ).body

    customer_id = bootstrap["customerUserId"]
    player_id = bootstrap["playerUserId"]
    admin_id = bootstrap["adminUserId"]
    other_players = [
        item["userId"]
        for item in identities["players"]
        if item["userId"] != player_id
    ]
    if not other_players:
        raise AssertionError("need at least two seeded players for authorization parity")

    customer_headers = {"X-User-Id": customer_id}
    player_headers = {"X-User-Id": player_id}
    other_player_headers = {"X-User-Id": other_players[0]}
    admin_headers = {"X-Admin-Id": admin_id}

    game = bootstrap["games"][0]
    sku = game["skus"][0]

    created = expect(
        call(
            args.python_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={
                "sku_id": sku["id"],
                "quantity": 1,
                "remark": "go-order-read-parity",
            },
        ),
        201,
        "FastAPI creates order",
    ).body
    order_id = created["id"]

    listed = assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/orders?limit=50",
        headers=customer_headers,
    )
    if not any(item["id"] == order_id for item in listed.body):
        raise AssertionError("new order missing from customer list")

    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}",
        headers=customer_headers,
    )
    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}/events",
        headers=customer_headers,
    )

    paid = expect(
        call(
            args.python_base,
            f"/api/v1/orders/{order_id}/mock-pay",
            method="POST",
            headers={
                **customer_headers,
                "Idempotency-Key": f"go-order-read-pay-{uuid.uuid4().hex}",
            },
        ),
        200,
        "FastAPI pays order",
    ).body

    expect(
        call(
            args.python_base,
            f"/api/v1/player/orders/{order_id}/claim",
            method="POST",
            headers=player_headers,
            body={"expected_version": paid["version"]},
        ),
        200,
        "FastAPI player claims order",
    )

    detail = assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}",
        headers=customer_headers,
    )
    if detail.body["service_player"]["binding"] != "ASSIGNED":
        raise AssertionError("assigned player projection missing after claim")

    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}",
        headers=player_headers,
    )
    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}/events",
        headers=player_headers,
    )
    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}",
        headers=admin_headers,
    )

    denied = assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{order_id}",
        headers=other_player_headers,
    )
    if denied.status != 403 or denied.body.get("detail") != "ORDER_ACCESS_DENIED":
        raise AssertionError(f"unexpected unrelated-player denial: {denied.body!r}")

    missing = "00000000-0000-0000-0000-000000000000"
    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/orders/{missing}",
        headers=customer_headers,
    )

    assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/orders/not-a-uuid",
        headers=customer_headers,
        compare_body=False,
    )
    for path in (
        "/api/v1/orders?limit=",
        "/api/v1/orders?limit=0",
        "/api/v1/orders?limit=101",
    ):
        assert_same(
            args.python_base,
            args.go_base,
            path,
            headers=customer_headers,
            compare_body=False,
        )

    print("M3 order read parity PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"M3 order read parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
