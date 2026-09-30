#!/usr/bin/env python3
"""Generate and validate the Mini Program starter theme from one source."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "apps" / "miniapp"
THEME_PATH = MINIAPP / "theme.json"
CSS_PATH = MINIAPP / "src" / "styles" / "theme.css"
TS_PATH = MINIAPP / "src" / "ui" / "theme.ts"
PAGES_PATH = MINIAPP / "src" / "pages.json"

CSS_NAMES = {
    "brand": "brand",
    "brandStrong": "brand-strong",
    "brandSoft": "brand-soft",
    "brandGhost": "brand-ghost",
    "ink": "ink",
    "ink2": "ink-2",
    "muted": "muted",
    "muted2": "muted-2",
    "bg": "bg",
    "surface": "surface",
    "surface2": "surface-2",
    "line": "line",
    "neutral": "neutral",
    "neutralSoft": "neutral-soft",
    "success": "success",
    "successSoft": "success-soft",
    "warning": "warning",
    "warningSoft": "warning-soft",
    "danger": "danger",
    "dangerSoft": "danger-soft",
    "inverseBg": "inverse-bg",
    "inverseSurface": "inverse-surface",
    "inverseControl": "inverse-control",
    "inverseControlStrong": "inverse-control-strong",
    "inverseMuted": "inverse-muted",
    "inverseTextSoft": "inverse-text-soft",
    "brandOnInverse": "brand-on-inverse",
    "successOnInverse": "success-on-inverse",
    "warningOnInverse": "warning-on-inverse",
    "dangerOnInverse": "danger-on-inverse",
}

PROTECTED_KEYS = {
    "brand",
    "brandStrong",
    "brandSoft",
    "brandGhost",
    "danger",
    "inverseBg",
    "inverseSurface",
    "inverseControl",
    "inverseControlStrong",
    "brandOnInverse",
    "successOnInverse",
    "warningOnInverse",
    "dangerOnInverse",
}


def load_theme() -> dict:
    data = json.loads(THEME_PATH.read_text(encoding="utf-8"))
    colors = data.get("colors", {})
    chrome = data.get("chrome", {})

    missing_colors = sorted(set(CSS_NAMES) - set(colors))
    required_chrome = {
        "lightNavigation",
        "darkNavigation",
        "tabText",
        "tabSelected",
        "tabBackground",
    }
    missing_chrome = sorted(required_chrome - set(chrome))
    if missing_colors or missing_chrome:
        raise SystemExit(
            f"theme.json missing colors={missing_colors} chrome={missing_chrome}"
        )

    color_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
    for group_name, group in (("colors", colors), ("chrome", chrome)):
        for key, value in group.items():
            if not isinstance(value, str) or not color_pattern.fullmatch(value):
                raise SystemExit(
                    f"theme.json {group_name}.{key} must be a 6-digit hex color"
                )
    return data


def render_css(colors: dict[str, str]) -> str:
    lines = [
        "/*",
        " * Generated from apps/miniapp/theme.json by scripts/sync_miniapp_theme.py.",
        " * Edit theme.json, then run: npm run theme:sync",
        " */",
        "page {",
    ]
    for key, css_name in CSS_NAMES.items():
        lines.append(f"  --{css_name}: {colors[key]};")
    lines.extend(["}", ""])
    return "\n".join(lines)


def render_ts(colors: dict[str, str]) -> str:
    lines = [
        "/*",
        " * Generated from apps/miniapp/theme.json by scripts/sync_miniapp_theme.py.",
        " * Edit theme.json, then run: npm run theme:sync",
        " */",
        "export const themeColors = {",
    ]
    entries = list(CSS_NAMES)
    for index, key in enumerate(entries):
        suffix = "," if index < len(entries) - 1 else ""
        lines.append(f'  {key}: "{colors[key]}"{suffix}')
    lines.extend(["} as const", ""])
    return "\n".join(lines)


def themed_pages(source: dict, chrome: dict[str, str]) -> dict:
    data = json.loads(json.dumps(source))

    for page in data.get("pages", []):
        style = page.get("style", {})
        if "navigationBarBackgroundColor" in style:
            style["navigationBarBackgroundColor"] = chrome["lightNavigation"]

    for package in data.get("subPackages", []):
        for page in package.get("pages", []):
            style = page.get("style", {})
            if "navigationBarBackgroundColor" not in style:
                continue
            style["navigationBarBackgroundColor"] = (
                chrome["darkNavigation"]
                if style.get("navigationBarTextStyle") == "white"
                else chrome["lightNavigation"]
            )

    tab_bar = data.get("tabBar", {})
    tab_bar["color"] = chrome["tabText"]
    tab_bar["selectedColor"] = chrome["tabSelected"]
    tab_bar["backgroundColor"] = chrome["tabBackground"]
    return data


def find_palette_leaks(colors: dict[str, str]) -> list[str]:
    protected = {
        colors[key].lower(): key
        for key in PROTECTED_KEYS
    }
    violations: list[str] = []
    src = MINIAPP / "src"

    for path in sorted(src.rglob("*")):
        if path.suffix not in {".vue", ".css", ".ts"}:
            continue
        if path in {CSS_PATH, TS_PATH}:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            lower = line.lower()
            for value, key in protected.items():
                if value in lower:
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line_number}: "
                        f"{value} duplicates theme color {key}; use the semantic token"
                    )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    theme = load_theme()
    colors = theme["colors"]
    chrome = theme["chrome"]
    expected_css = render_css(colors)
    expected_ts = render_ts(colors)

    pages_source = json.loads(PAGES_PATH.read_text(encoding="utf-8"))
    expected_pages = themed_pages(pages_source, chrome)

    if args.check:
        violations: list[str] = []
        if CSS_PATH.read_text(encoding="utf-8") != expected_css:
            violations.append(
                "apps/miniapp/src/styles/theme.css is stale; run npm run theme:sync"
            )
        if TS_PATH.read_text(encoding="utf-8") != expected_ts:
            violations.append(
                "apps/miniapp/src/ui/theme.ts is stale; run npm run theme:sync"
            )
        if pages_source != expected_pages:
            violations.append(
                "apps/miniapp/src/pages.json chrome colors are stale; "
                "run npm run theme:sync"
            )
        violations.extend(find_palette_leaks(colors))
        if violations:
            print("Mini Program theme contract violations:")
            print("\n".join(f"- {item}" for item in violations))
            return 1
        print("Mini Program theme contract: PASS")
        return 0

    CSS_PATH.write_text(expected_css, encoding="utf-8")
    TS_PATH.write_text(expected_ts, encoding="utf-8")
    PAGES_PATH.write_text(
        json.dumps(expected_pages, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Mini Program theme synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
