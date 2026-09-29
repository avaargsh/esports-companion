#!/usr/bin/env python3
import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_ENV = (
    "WECHAT_APP_ID",
    "WECHAT_MCH_ID",
    "WECHAT_MCH_CERT_SERIAL",
    "WECHAT_NOTIFY_URL",
    "WECHAT_REFUND_NOTIFY_URL",
    "WECHAT_PAY_PLATFORM_CERT_SERIAL",
    "CORS_ALLOWED_ORIGINS",
)
REQUIRED_SECRETS = (
    "postgres_password",
    "session_signing_key",
    "wechat_app_secret",
    "wechat_mch_private_key",
    "wechat_pay_api_v3_key",
    "wechat_platform_certificate",
)
PLACEHOLDERS = ("replace-me", "example.com", "changeme", "change-me")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def fail(errors: list[str]) -> int:
    for item in errors:
        print(f"[staging-preflight] ERROR {item}", file=sys.stderr)
    print(
        f"[staging-preflight] FAIL errors={len(errors)}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env.staging")
    parser.add_argument(
        "--secrets-dir",
        default="deploy/secrets-staging",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    secrets_dir = Path(args.secrets_dir)
    errors: list[str] = []

    if not env_path.is_file():
        return fail([f"missing env file: {env_path}"])

    env = load_env(env_path)

    if env.get("APP_ENV") != "staging":
        errors.append("APP_ENV must be staging")
    for name in ("AUTH_PROVIDER", "PAYMENT_PROVIDER", "REFUND_PROVIDER"):
        if env.get(name, "").lower() != "wechat":
            errors.append(f"{name} must be wechat")

    for name in REQUIRED_ENV:
        value = env.get(name, "")
        if not value:
            errors.append(f"{name} is required")
            continue
        if any(token in value.lower() for token in PLACEHOLDERS):
            errors.append(f"{name} still contains a placeholder")

    app_id = env.get("WECHAT_APP_ID", "")
    if app_id and not re.fullmatch(r"wx[0-9A-Za-z]{8,}", app_id):
        errors.append("WECHAT_APP_ID does not look like a Mini Program AppID")

    for name in ("WECHAT_NOTIFY_URL", "WECHAT_REFUND_NOTIFY_URL"):
        value = env.get(name, "")
        if value and not is_https_url(value):
            errors.append(f"{name} must be HTTPS")

    cors = [
        item.strip()
        for item in env.get("CORS_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    ]
    if not cors or any(not is_https_url(item) for item in cors):
        errors.append("CORS_ALLOWED_ORIGINS must contain HTTPS origins only")

    for name in REQUIRED_SECRETS:
        path = secrets_dir / name
        if not path.is_file():
            errors.append(f"missing secret file: {path}")
            continue
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            errors.append(f"empty secret file: {path}")
            continue
        if name == "session_signing_key" and len(value) < 32:
            errors.append("session_signing_key must be at least 32 characters")
        if name == "wechat_pay_api_v3_key" and len(value.encode()) != 32:
            errors.append("wechat_pay_api_v3_key must be exactly 32 bytes")
        if name == "wechat_mch_private_key" and "PRIVATE KEY" not in value:
            errors.append("wechat_mch_private_key is not PEM private key material")
        if (
            name == "wechat_platform_certificate"
            and "BEGIN CERTIFICATE" not in value
        ):
            errors.append("wechat_platform_certificate is not PEM certificate material")

    if errors:
        return fail(errors)

    print(
        "[staging-preflight] PASS "
        f"env={env_path} secrets={secrets_dir} "
        f"app_id={env['WECHAT_APP_ID']} "
        f"payment_callback={env['WECHAT_NOTIFY_URL']} "
        f"refund_callback={env['WECHAT_REFUND_NOTIFY_URL']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
