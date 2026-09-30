#!/usr/bin/env python3
"""Enforce Mini Program interaction and starter-theme contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "apps" / "miniapp" / "src"
PAGE_ROOTS = (MINIAPP / "pages", MINIAPP / "pages-player")
FOUNDATION = MINIAPP / "styles" / "foundation.css"
THEME = MINIAPP / "styles" / "theme.css"

FORBIDDEN_FEEDBACK = (
    "uni.showToast",
    "uni.showModal",
    "uni.showLoading",
    "uni.hideLoading",
)
THEME_TOKENS = (
    "--brand:",
    "--brand-soft:",
    "--ink:",
    "--muted:",
    "--bg:",
    "--surface:",
    "--line:",
    "--success:",
    "--warning:",
    "--danger:",
    "--provider-bg:",
)


def check_feedback(violations: list[str]) -> None:
    for page_root in PAGE_ROOTS:
        for path in sorted(page_root.rglob("*.vue")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                for token in FORBIDDEN_FEEDBACK:
                    if token in line:
                        relative = path.relative_to(ROOT)
                        violations.append(
                            f"{relative}:{line_number}: direct {token} is forbidden; "
                            "use src/ui/feedback.ts"
                        )


def check_theme(violations: list[str]) -> None:
    theme = THEME.read_text(encoding="utf-8")
    foundation = FOUNDATION.read_text(encoding="utf-8")

    for token in THEME_TOKENS:
        if token not in theme:
            violations.append(
                f"{THEME.relative_to(ROOT)}: required theme token {token} is missing"
            )
        if token in foundation:
            violations.append(
                f"{FOUNDATION.relative_to(ROOT)}: theme token {token} belongs in theme.css"
            )


def main() -> int:
    violations: list[str] = []
    check_feedback(violations)
    check_theme(violations)

    if violations:
        print("Mini Program UI contract violations:")
        print("\n".join(f"- {item}" for item in violations))
        return 1

    print("Mini Program UI contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
