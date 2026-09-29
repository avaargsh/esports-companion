#!/usr/bin/env python3
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def get(base: str, path: str) -> tuple[int, str]:
    req = Request(base.rstrip("/") + path, method="GET")
    try:
        with urlopen(req, timeout=10) as response:  # nosec B310
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"{path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    checks = {}
    status, body = get(args.base_url, "/livez")
    checks["livez"] = status
    if status != 200:
        raise RuntimeError(f"/livez expected 200, got {status}: {body}")

    status, body = get(args.base_url, "/readyz")
    checks["readyz"] = status
    if status != 200:
        raise RuntimeError(f"/readyz expected 200, got {status}: {body}")

    status, _ = get(args.base_url, "/api/v1/dev/bootstrap")
    checks["dev_bootstrap"] = status
    if status != 404:
        raise RuntimeError(
            f"secure staging exposed /api/v1/dev/bootstrap: HTTP {status}"
        )

    status, _ = get(args.base_url, "/metrics")
    checks["public_metrics"] = status
    if status != 404:
        raise RuntimeError(
            f"staging ingress exposed /metrics publicly: HTTP {status}"
        )

    print(json.dumps({"status": "PASS", "checks": checks}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"[staging-endpoints] FAIL {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
