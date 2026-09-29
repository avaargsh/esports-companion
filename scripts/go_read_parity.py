#!/usr/bin/env python3
"""Compare M1 read contracts between FastAPI and the Go migration target."""

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


def fetch(base: str, path: str) -> Response:
    request = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = response.read()
            return Response(response.status, json.loads(payload))
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return Response(exc.code, json.loads(payload))


def assert_same(
    python_base: str,
    go_base: str,
    path: str,
    *,
    compare_body: bool = True,
) -> Response:
    left = fetch(python_base, path)
    right = fetch(go_base, path)

    if left.status != right.status:
        raise AssertionError(
            f"{path}: status mismatch FastAPI={left.status} Go={right.status}"
        )
    if compare_body and left.body != right.body:
        raise AssertionError(
            f"{path}: body mismatch\n"
            f"FastAPI={json.dumps(left.body, ensure_ascii=False, sort_keys=True)}\n"
            f"Go={json.dumps(right.body, ensure_ascii=False, sort_keys=True)}"
        )

    print(f"PASS {path} status={left.status}")
    return left


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    games = assert_same(args.python_base, args.go_base, "/api/v1/games")
    for game in games.body:
        assert_same(
            args.python_base,
            args.go_base,
            f"/api/v1/games/{game['id']}/skus",
        )

    players = assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/players?limit=12",
    )

    # Empty rank is intentionally a no-op in the existing FastAPI contract.
    assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/players?rank=&limit=12",
    )

    for player in players.body[:3]:
        assert_same(
            args.python_base,
            args.go_base,
            f"/api/v1/players/{player['id']}",
        )

    missing = "00000000-0000-0000-0000-000000000000"
    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/players/{missing}",
    )

    # Pydantic and the Go compatibility layer may format validation detail
    # differently; status parity is the invariant at M1.
    assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/players?limit=",
        compare_body=False,
    )
    assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/players?game_id=",
        compare_body=False,
    )

    print("M1 read parity PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError) as exc:
        print(f"M1 read parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
