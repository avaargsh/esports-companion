#!/usr/bin/env python3
"""Verify M2 auth/session interoperability between FastAPI and Go."""

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
    headers: dict[str, str] | None = None,
) -> Response:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return Response(
                response.status,
                json.loads(raw) if raw else None,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return Response(
            exc.code,
            json.loads(raw) if raw else None,
        )


def expect_status(response: Response, status: int, label: str) -> None:
    if response.status != status:
        raise AssertionError(
            f"{label}: expected status={status}, got={response.status} body={response.body}"
        )


def expect_detail(response: Response, status: int, detail: str, label: str) -> None:
    expect_status(response, status, label)
    if not isinstance(response.body, dict) or response.body.get("detail") != detail:
        raise AssertionError(
            f"{label}: expected detail={detail!r}, got={response.body!r}"
        )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    # FastAPI issues the first session; Go must accept its JWT and refresh token.
    py_login = call(
        args.python_base,
        "/api/v1/auth/wechat/login",
        method="POST",
        body={"code": "demo-customer"},
    )
    expect_status(py_login, 200, "python login")
    py_tokens = py_login.body

    go_me = call(
        args.go_base,
        "/api/v1/auth/me",
        headers=bearer(py_tokens["accessToken"]),
    )
    expect_status(go_me, 200, "Go accepts FastAPI access token")
    if go_me.body["userId"] != py_tokens["userId"] or go_me.body["roles"] != py_tokens["roles"]:
        raise AssertionError("Go principal differs from FastAPI login principal")

    go_refresh = call(
        args.go_base,
        "/api/v1/auth/refresh",
        method="POST",
        body={"refreshToken": py_tokens["refreshToken"]},
    )
    expect_status(go_refresh, 200, "Go rotates FastAPI refresh token")
    go_tokens = go_refresh.body

    expect_detail(
        call(
            args.python_base,
            "/api/v1/auth/me",
            headers=bearer(py_tokens["accessToken"]),
        ),
        401,
        "ACCESS_SESSION_REVOKED",
        "FastAPI sees Go rotation",
    )
    expect_status(
        call(
            args.python_base,
            "/api/v1/auth/me",
            headers=bearer(go_tokens["accessToken"]),
        ),
        200,
        "FastAPI accepts Go access token",
    )

    # Reusing the old token on FastAPI must revoke the Go-created descendant.
    expect_detail(
        call(
            args.python_base,
            "/api/v1/auth/refresh",
            method="POST",
            body={"refreshToken": py_tokens["refreshToken"]},
        ),
        401,
        "REFRESH_TOKEN_REUSED",
        "FastAPI detects reused pre-Go refresh token",
    )
    expect_detail(
        call(
            args.go_base,
            "/api/v1/auth/me",
            headers=bearer(go_tokens["accessToken"]),
        ),
        401,
        "ACCESS_SESSION_REVOKED",
        "Go sees descendant-family revocation from FastAPI",
    )

    # Reverse direction with a player role: Go issues, FastAPI authenticates.
    go_login = call(
        args.go_base,
        "/api/v1/auth/wechat/login",
        method="POST",
        body={"code": "demo-player-1"},
    )
    expect_status(go_login, 200, "Go player login")
    player_tokens = go_login.body
    if "PLAYER" not in player_tokens["roles"]:
        raise AssertionError(f"Go login did not derive PLAYER role: {player_tokens['roles']}")

    py_me = call(
        args.python_base,
        "/api/v1/auth/me",
        headers=bearer(player_tokens["accessToken"]),
    )
    expect_status(py_me, 200, "FastAPI accepts Go player access token")
    if py_me.body["roles"] != player_tokens["roles"]:
        raise AssertionError("FastAPI recomputed roles differ from Go")

    py_refresh = call(
        args.python_base,
        "/api/v1/auth/refresh",
        method="POST",
        body={"refreshToken": player_tokens["refreshToken"]},
    )
    expect_status(py_refresh, 200, "FastAPI rotates Go refresh token")
    py_rotated = py_refresh.body

    expect_status(
        call(
            args.go_base,
            "/api/v1/auth/me",
            headers=bearer(py_rotated["accessToken"]),
        ),
        200,
        "Go accepts FastAPI rotated access token",
    )

    logout = call(
        args.go_base,
        "/api/v1/auth/logout",
        method="POST",
        body={"refreshToken": py_rotated["refreshToken"]},
    )
    expect_status(logout, 204, "Go logs out FastAPI-created session")
    expect_detail(
        call(
            args.python_base,
            "/api/v1/auth/me",
            headers=bearer(py_rotated["accessToken"]),
        ),
        401,
        "ACCESS_SESSION_REVOKED",
        "FastAPI sees Go logout",
    )

    print("M2 auth/session parity PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"M2 auth/session parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
