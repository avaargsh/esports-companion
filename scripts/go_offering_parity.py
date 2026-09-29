#!/usr/bin/env python3
"""Verify protected provider-offering interoperability between FastAPI and Go."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
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
    token: str | None = None,
) -> Response:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        headers=headers,
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


def login(base: str, code: str) -> dict[str, Any]:
    return expect(
        call(
            base,
            "/api/v1/auth/wechat/login",
            method="POST",
            body={"code": code},
        ),
        200,
        f"login {code}",
    ).body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    customer = login(args.go_base, "demo-customer")
    for base, label in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        denied = expect(
            call(base, "/api/v1/player/offerings", token=customer["accessToken"]),
            403,
            f"{label} denies USER offering access",
        )
        if denied.body.get("detail") != "PLAYER_REQUIRED":
            raise AssertionError(f"{label} unexpected USER denial: {denied.body!r}")

    player = login(args.go_base, "demo-player-1")
    token = player["accessToken"]

    py_before = expect(
        call(args.python_base, "/api/v1/player/offerings", token=token),
        200,
        "FastAPI offering list",
    )
    go_before = expect(
        call(args.go_base, "/api/v1/player/offerings", token=token),
        200,
        "Go offering list",
    )
    if py_before.body != go_before.body:
        raise AssertionError(
            f"initial offering list mismatch FastAPI={py_before.body!r} Go={go_before.body!r}"
        )

    games = expect(call(args.python_base, "/api/v1/games"), 200, "games").body
    if not games:
        raise AssertionError("seed has no games")
    skus = expect(
        call(args.python_base, f"/api/v1/games/{games[0]['id']}/skus"),
        200,
        "skus",
    ).body
    if not skus:
        raise AssertionError("seed has no skus")
    sku_id = skus[0]["id"]

    python_write = expect(
        call(
            args.python_base,
            f"/api/v1/player/offerings/{sku_id}",
            method="PUT",
            token=token,
            body={
                "price_override": 3456,
                "description": "python-to-go parity",
                "status": "ACTIVE",
            },
        ),
        200,
        "FastAPI writes offering",
    )
    go_after_python = expect(
        call(args.go_base, "/api/v1/player/offerings", token=token),
        200,
        "Go reads FastAPI offering",
    )
    if python_write.body not in go_after_python.body:
        raise AssertionError("Go did not observe FastAPI offering write")

    go_write = expect(
        call(
            args.go_base,
            f"/api/v1/player/offerings/{sku_id}",
            method="PUT",
            token=token,
            body={
                "price_override": 3210,
                "description": "go-to-python parity",
                "status": "INACTIVE",
            },
        ),
        200,
        "Go writes offering",
    )
    py_after_go = expect(
        call(args.python_base, "/api/v1/player/offerings", token=token),
        200,
        "FastAPI reads Go offering",
    )
    if go_write.body not in py_after_go.body:
        raise AssertionError("FastAPI did not observe Go offering write")

    missing = "00000000-0000-0000-0000-000000000000"
    for base, label in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        missing_resp = expect(
            call(
                base,
                f"/api/v1/player/offerings/{missing}",
                method="PUT",
                token=token,
                body={"status": "ACTIVE"},
            ),
            404,
            f"{label} rejects missing SKU",
        )
        if missing_resp.body.get("detail") != "SKU_NOT_FOUND":
            raise AssertionError(f"{label} missing SKU detail mismatch")

        invalid_status = expect(
            call(
                base,
                f"/api/v1/player/offerings/{sku_id}",
                method="PUT",
                token=token,
                body={"status": "BROKEN"},
            ),
            409,
            f"{label} rejects invalid offering status",
        )
        if invalid_status.body.get("detail") != "INVALID_OFFERING_STATUS":
            raise AssertionError(f"{label} invalid status detail mismatch")

    print("M2.1 provider offering parity PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"M2.1 provider offering parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
