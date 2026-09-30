#!/usr/bin/env python3
"""Validate the declared Mini Program starter extraction surface."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "apps" / "miniapp" / "starter.manifest.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    includes = data.get("include", [])
    product_roots = data.get("excludeProductRoots", [])
    violations: list[str] = []

    if data.get("schemaVersion") != 1:
        violations.append("starter.manifest.json schemaVersion must be 1")

    if not includes:
        violations.append("starter.manifest.json include must not be empty")

    for relative in includes:
        path = ROOT / relative
        if not path.exists():
            violations.append(f"starter include does not exist: {relative}")
        for product_root in product_roots:
            if relative == product_root or relative.startswith(product_root + "/"):
                violations.append(
                    f"starter include crosses into product root: {relative}"
                )

    required = {
        "apps/miniapp/theme.json",
        "apps/miniapp/src/platform",
        "apps/miniapp/src/ui",
        "apps/miniapp/src/components/ui",
        "scripts/sync_miniapp_theme.py",
        "scripts/check_miniapp_starter_boundary.py",
        "docs/miniapp-starter-boundary.md",
    }
    missing = sorted(required - set(includes))
    for relative in missing:
        violations.append(f"starter manifest missing required surface: {relative}")

    if len(includes) != len(set(includes)):
        violations.append("starter.manifest.json include contains duplicates")

    if violations:
        print("Mini Program starter manifest violations:")
        print("\n".join(f"- {item}" for item in violations))
        return 1

    print(f"Mini Program starter manifest: PASS ({len(includes)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
