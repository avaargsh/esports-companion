#!/usr/bin/env python3
"""Generate ephemeral WeChat callback crypto material for dual-runtime parity."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-env", required=True)
    args = parser.parse_args()

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "wechat-parity-platform")]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(hours=2))
        .sign(key, hashes.SHA256())
    )

    key_path = Path("/tmp/wechat-parity-platform-key.pem")
    cert_path = Path("/tmp/wechat-parity-platform-cert.pem")
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    serial = format(certificate.serial_number, "X")
    github_env = Path(args.github_env)
    with github_env.open("a", encoding="utf-8") as handle:
        handle.write("WECHAT_APP_ID=wx-parity-app\n")
        handle.write("WECHAT_MCH_ID=mch-parity\n")
        handle.write(
            "WECHAT_PAY_API_V3_KEY=0123456789abcdef0123456789abcdef\n"
        )
        handle.write(f"WECHAT_PAY_PLATFORM_CERT_SERIAL={serial}\n")
        handle.write(
            f"WECHAT_PAY_PLATFORM_CERTIFICATE_FILE={cert_path}\n"
        )
        handle.write(f"WECHAT_TEST_PLATFORM_PRIVATE_KEY_FILE={key_path}\n")

    print(f"generated parity platform certificate serial={serial}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
