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
            return Response(response.status, json.loads(response.read()))
    except urllib.error.HTTPError as exc:
        return Response(exc.code, json.loads(exc.read()))


def assert_same(
    python_base: str,
    go_base: str,
    path: str,
    *,
    compare_body: bool = True,
) -> Response:
    reference = fetch(python_base, path)
    target = fetch(go_base, path)

    if reference.status != target.status:
        raise AssertionError(
            f"{path}: status mismatch FastAPI={reference.status} Go={target.status}"
        )
    if compare_body and reference.body != target.body:
        raise AssertionError(
            f"{path}: body mismatch\n"
            f"FastAPI={json.dumps(reference.body, ensure_ascii=False, sort_keys=True)}\n"
            f"Go={json.dumps(target.body, ensure_ascii=False, sort_keys=True)}"
        )

    print(f"PASS {path} status={reference.status}")
    return reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    games = assert_same(args.python_base, args.go_base, "/api/v1/games")
    for game in games.body:
        game_id = game["id"]
        assert_same(
            args.python_base,
            args.go_base,
            f"/api/v1/games/{game_id}/skus",
        )
        # This is the actual Mini Program discovery request shape.
        assert_same(
            args.python_base,
            args.go_base,
            f"/api/v1/players?limit=30&game_id={game_id}",
        )

    if games.body:
        compact = games.body[0]["id"].replace("-", "")
        assert_same(
            args.python_base,
            args.go_base,
            f"/api/v1/games/{compact}/skus",
        )

    missing = "00000000-0000-0000-0000-000000000000"
    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/games/{missing}/skus",
    )

    players = assert_same(
        args.python_base,
        args.go_base,
        "/api/v1/players?limit=12",
    )
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

    assert_same(
        args.python_base,
        args.go_base,
        f"/api/v1/players/{missing}",
    )

    # Validation detail formatting remains framework-specific in M1. Status
    # parity is the invariant for invalid typed inputs.
    for invalid_path in (
        "/api/v1/players?limit=",
        "/api/v1/players?limit=0",
        "/api/v1/players?limit=51",
        "/api/v1/players?game_id=",
        "/api/v1/players/not-a-uuid",
    ):
        assert_same(
            args.python_base,
            args.go_base,
            invalid_path,
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
