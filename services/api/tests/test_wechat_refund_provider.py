import base64
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from app.providers.refund import WeChatRefundProvider


def _private_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _platform_certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "wechat-refund-submit-test")]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return (
        key,
        cert.public_bytes(serialization.Encoding.PEM).decode("utf-8"),
        format(cert.serial_number, "X"),
    )


def _signed_response(key, serial, payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    nonce = "refund-submit-response"
    message = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body + b"\n"
    signature = base64.b64encode(
        key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    return 200, {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": signature,
        "Wechatpay-Serial": serial,
    }, body


def test_wechat_refund_provider_uses_stable_out_refund_no_and_original_transaction():
    captured = {}
    platform_key, cert_pem, serial = _platform_certificate()

    def transport(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=body, timeout=timeout)
        return _signed_response(
            platform_key,
            serial,
            {
                "refund_id": "503000001",
                "out_refund_no": "RFD_test",
                "transaction_id": "420000001",
                "out_trade_no": "ORD_TEST",
                "status": "PROCESSING",
            },
        )

    provider = WeChatRefundProvider(
        mch_id="mch-1",
        cert_serial="serial-1",
        private_key=_private_key_pem(),
        notify_url="https://example.com/api/v1/refunds/wechat/callback",
        platform_cert_serial=serial,
        platform_certificate=cert_pem,
        transport=transport,
    )

    class StubRefund:
        amount = 3000
        out_refund_no = "RFD_test"

    class StubOrder:
        total_amount = 3000

    class StubPayment:
        provider = "WECHAT"
        status = "SUCCESS"
        provider_txn_id = "420000001"

    intent = provider.create_refund(
        refund=StubRefund(),
        order=StubOrder(),
        payment=StubPayment(),
        reason="Dispute refund",
    )

    payload = json.loads(captured["body"])
    assert captured["url"].endswith("/v3/refund/domestic/refunds")
    assert payload["transaction_id"] == "420000001"
    assert payload["out_refund_no"] == "RFD_test"
    assert payload["amount"] == {
        "refund": 3000,
        "total": 3000,
        "currency": "CNY",
    }
    assert payload["notify_url"].endswith("/api/v1/refunds/wechat/callback")
    assert captured["headers"]["Authorization"].startswith(
        "WECHATPAY2-SHA256-RSA2048 "
    )
    assert intent.provider_refund_id == "503000001"
    assert intent.status == "PROCESSING"


def test_wechat_refund_provider_rejects_unsigned_submit_response():
    _platform_key, cert_pem, serial = _platform_certificate()

    def transport(url, headers, body, timeout):
        response = json.dumps(
            {
                "refund_id": "503000001",
                "out_refund_no": "RFD_test",
                "status": "PROCESSING",
            }
        ).encode()
        return 200, {}, response

    provider = WeChatRefundProvider(
        mch_id="mch-1",
        cert_serial="serial-1",
        private_key=_private_key_pem(),
        notify_url="https://example.com/api/v1/refunds/wechat/callback",
        platform_cert_serial=serial,
        platform_certificate=cert_pem,
        transport=transport,
    )

    class StubRefund:
        amount = 3000
        out_refund_no = "RFD_test"

    class StubOrder:
        total_amount = 3000

    class StubPayment:
        provider = "WECHAT"
        status = "SUCCESS"
        provider_txn_id = "420000001"

    with pytest.raises(ValueError, match="WECHAT_REFUND_RESPONSE_SIGNATURE_HEADERS_MISSING"):
        provider.create_refund(
            refund=StubRefund(),
            order=StubOrder(),
            payment=StubPayment(),
            reason="Dispute refund",
        )
