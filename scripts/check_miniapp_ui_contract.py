#!/usr/bin/env python3
"""Fail when Mini Program pages bypass the shared interaction-feedback contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE_ROOTS = (
    ROOT / "apps" / "miniapp" / "src" / "pages",
    ROOT / "apps" / "miniapp" / "src" / "pages-player",
)
FORBIDDEN = (
    "uni.showToast",
    "uni.showModal",
    "uni.showLoading",
    "uni.hideLoading",
)


def main() -> int:
    violations: list[str] = []

    for page_root in PAGE_ROOTS:
        for path in sorted(page_root.rglob("*.vue")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                for token in FORBIDDEN:
                    if token in line:
                        relative = path.relative_to(ROOT)
                        violations.append(
                            f"{relative}:{line_number}: direct {token} is forbidden; "
                            "use src/ui/feedback.ts"
                        )

    if violations:
        print("Mini Program interaction contract violations:")
        print("\n".join(f"- {item}" for item in violations))
        return 1

    print("Mini Program interaction contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
