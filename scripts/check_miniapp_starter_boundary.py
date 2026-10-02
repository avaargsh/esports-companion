#!/usr/bin/env python3
"""Enforce the reusable Mini Program starter/platform boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "miniapp" / "src"
PLATFORM = SRC / "platform"

FORBIDDEN_PLATFORM_IMPORTS = (
    "../api",
    "../components",
    "../pages",
    "../pages-player",
    "../types",
    "../utils",
    "../ui",
)
FORBIDDEN_DOMAIN_MARKERS = (
    "/orders",
    "/player/",
    "/wallet",
    "/withdrawals",
    "OrderStatus",
    "PublicPlayer",
    "Withdrawal",
)


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def check_platform_dependencies(violations: list[str]) -> None:
    for path in sorted(PLATFORM.rglob("*.ts")):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)

        for marker in FORBIDDEN_PLATFORM_IMPORTS:
            if marker in text:
                violations.append(
                    f"{relative}: platform code must not import product layer {marker}"
                )

        for marker in FORBIDDEN_DOMAIN_MARKERS:
            offset = text.find(marker)
            if offset >= 0:
                violations.append(
                    f"{relative}:{line_number(text, offset)}: "
                    f"product-domain marker {marker!r} leaked into platform/"
                )


def check_transport_ownership(violations: list[str]) -> None:
    owner = SRC / "platform" / "http.ts"
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in {".ts", ".vue"} or path == owner:
            continue
        text = path.read_text(encoding="utf-8")
        offset = text.find("uni.request(")
        if offset >= 0:
            violations.append(
                f"{path.relative_to(ROOT)}:{line_number(text, offset)}: "
                "direct uni.request is forbidden; use platform/http.ts"
            )


def check_wechat_native_ownership(violations: list[str]) -> None:
    owner = SRC / "platform" / "wechat.ts"
    forbidden = (
        "uni.login(",
        "uni.requestPayment(",
        "requestSubscribeMessage(",
    )
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in {".ts", ".vue"} or path == owner:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            offset = text.find(marker)
            if offset >= 0:
                violations.append(
                    f"{path.relative_to(ROOT)}:{line_number(text, offset)}: "
                    f"direct WeChat capability {marker!r} is forbidden; "
                    "use platform/wechat.ts"
                )


def check_environment_ownership(violations: list[str]) -> None:
    owner = SRC / "platform" / "env.ts"
    allowed = {owner, SRC / "env.d.ts"}
    for path in sorted(SRC.rglob("*.ts")):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        offset = text.find("import.meta.env.VITE_")
        if offset >= 0:
            violations.append(
                f"{path.relative_to(ROOT)}:{line_number(text, offset)}: "
                "runtime env access is centralized in platform/env.ts"
            )


def check_required_adapters(violations: list[str]) -> None:
    client = (SRC / "api" / "client.ts").read_text(encoding="utf-8")
    config = (SRC / "api" / "config.ts").read_text(encoding="utf-8")
    auth = (SRC / "api" / "auth.ts").read_text(encoding="utf-8")

    if 'from "../platform/http"' not in client or "createHttpClient" not in client:
        violations.append(
            "apps/miniapp/src/api/client.ts must compose platform/http.ts"
        )

    if 'from "../platform/env"' not in config:
        violations.append(
            "apps/miniapp/src/api/config.ts must remain a platform/env.ts facade"
        )

    if 'from "../platform/session"' not in auth:
        violations.append(
            "apps/miniapp/src/api/auth.ts must compose platform/session.ts"
        )


def main() -> int:
    violations: list[str] = []
    check_platform_dependencies(violations)
    check_transport_ownership(violations)
    check_wechat_native_ownership(violations)
    check_environment_ownership(violations)
    check_required_adapters(violations)

    if violations:
        print("Mini Program starter boundary violations:")
        print("\n".join(f"- {item}" for item in violations))
        return 1

    print("Mini Program starter boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
