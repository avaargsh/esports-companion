#!/usr/bin/env python3
"""Extract the declared Mini Program starter into a standalone smoke-test workspace."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "apps" / "miniapp"
MANIFEST = MINIAPP / "starter.manifest.json"
SOURCE_PACKAGE = MINIAPP / "package.json"


def copy_surface(destination_root: Path, includes: list[str]) -> None:
    for relative in includes:
        source = ROOT / relative
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)


def render_package(source: dict) -> dict:
    return {
        "name": "@starter/miniapp-smoke",
        "version": "0.0.0",
        "private": True,
        "license": source.get("license", "Apache-2.0"),
        "scripts": {
            "build:mp-weixin": "uni build -p mp-weixin",
            "type-check": "vue-tsc --noEmit",
            "theme:check": "python3 ../../scripts/sync_miniapp_theme.py --check",
        },
        "dependencies": source["dependencies"],
        "devDependencies": source["devDependencies"],
    }


def write_scaffold(destination_root: Path) -> None:
    app = destination_root / "apps" / "miniapp"
    src = app / "src"
    src.mkdir(parents=True, exist_ok=True)

    source_package = json.loads(SOURCE_PACKAGE.read_text(encoding="utf-8"))
    (app / "package.json").write_text(
        json.dumps(render_package(source_package), indent=2) + "\n",
        encoding="utf-8",
    )

    (app / "vite.config.ts").write_text(
        'import { defineConfig } from "vite"\n'
        'import uni from "@dcloudio/vite-plugin-uni"\n\n'
        "export default defineConfig({ plugins: [uni()] })\n",
        encoding="utf-8",
    )

    (app / "tsconfig.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "Node",
                    "strict": True,
                    "jsx": "preserve",
                    "resolveJsonModule": True,
                    "esModuleInterop": True,
                    "lib": ["ES2022", "DOM"],
                    "types": ["vite/client", "node", "@dcloudio/types"],
                    "skipLibCheck": True,
                },
                "include": [
                    "src/**/*.ts",
                    "src/**/*.d.ts",
                    "src/**/*.vue",
                    "vite.config.ts",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (src / "main.ts").write_text(
        'import { createSSRApp } from "vue"\n'
        'import App from "./App.vue"\n\n'
        "export function createApp() {\n"
        "  const app = createSSRApp(App)\n"
        "  return { app }\n"
        "}\n",
        encoding="utf-8",
    )

    (src / "App.vue").write_text(
        "<script lang=\"ts\">\n"
        "export default {}\n"
        "</script>\n\n"
        "<style>\n"
        '@import "./styles/theme.css";\n'
        '@import "./styles/foundation.css";\n'
        "</style>\n",
        encoding="utf-8",
    )

    (src / "env.d.ts").write_text(
        '/// <reference types="vite/client" />\n'
        '/// <reference types="@dcloudio/types" />\n\n'
        "interface ImportMetaEnv {\n"
        "  readonly VITE_API_ORIGIN?: string\n"
        '  readonly VITE_AUTH_MODE?: "demo" | "wechat"\n'
        "}\n\n"
        "interface ImportMeta {\n"
        "  readonly env: ImportMetaEnv\n"
        "}\n",
        encoding="utf-8",
    )

    (src / "manifest.json").write_text(
        json.dumps(
            {
                "name": "miniapp-starter-smoke",
                "appid": "__UNI__MINIAPP_STARTER",
                "description": "Standalone extraction smoke test",
                "versionName": "0.0.0",
                "versionCode": "1",
                "mp-weixin": {
                    "appid": "",
                    "setting": {"urlCheck": False},
                    "usingComponents": True,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    theme = json.loads((app / "theme.json").read_text(encoding="utf-8"))
    light_navigation = theme["chrome"]["lightNavigation"]
    (src / "pages.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "path": "pages-lab/ui/index",
                        "style": {
                            "navigationBarTitleText": "UI Showcase",
                            "navigationBarBackgroundColor": light_navigation,
                            "navigationBarTextStyle": "black",
                        },
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def verify_extraction(destination_root: Path, product_roots: list[str]) -> None:
    violations: list[str] = []
    for relative in product_roots:
        if (destination_root / relative).exists():
            violations.append(f"product root leaked into extraction: {relative}")

    required = [
        "apps/miniapp/package.json",
        "apps/miniapp/src/main.ts",
        "apps/miniapp/src/App.vue",
        "apps/miniapp/src/pages.json",
        "apps/miniapp/src/manifest.json",
        "apps/miniapp/src/platform",
        "apps/miniapp/src/components/ui",
        "apps/miniapp/src/pages-lab/ui/index.vue",
    ]
    for relative in required:
        if not (destination_root / relative).exists():
            violations.append(f"standalone scaffold missing: {relative}")

    if violations:
        raise SystemExit("\n".join(violations))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    destination = args.output.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("output must be outside the repository root")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    copy_surface(destination, data["include"])
    write_scaffold(destination)
    verify_extraction(destination, data["excludeProductRoots"])

    print(f"Mini Program starter extracted to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
