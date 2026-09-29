import base64
import json
import time
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from app.providers.refund import WeChatRefundProvider


def _merchant_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _platform_certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "wechat-query-test")]
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


def test_wechat_refund_query_verifies_signed_response():
    platform_key, cert_pem, serial = _platform_certificate()

    def query_transport(url, headers, timeout):
        assert url.endswith("/v3/refund/domestic/refunds/RFD_test")
        assert headers["Authorization"].startswith("WECHATPAY2-SHA256-RSA2048 ")
        payload = {
            "refund_id": "503000001",
            "out_refund_no": "RFD_test",
            "transaction_id": "420000001",
            "out_trade_no": "ORD_TEST",
            "status": "SUCCESS",
            "amount": {
                "total": 3000,
                "refund": 3000,
                "payer_total": 3000,
                "payer_refund": 3000,
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        nonce = "query-response-nonce"
        message = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body + b"\n"
        signature = base64.b64encode(
            platform_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        ).decode()
        return 200, {
            "Wechatpay-Timestamp": timestamp,
            "Wechatpay-Nonce": nonce,
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": serial,
        }, body

    provider = WeChatRefundProvider(
        mch_id="mch-1",
        cert_serial="merchant-serial",
        private_key=_merchant_key_pem(),
        notify_url="https://example.com/refund-callback",
        platform_cert_serial=serial,
        platform_certificate=cert_pem,
        query_transport=query_transport,
    )

    class StubRefund:
        out_refund_no = "RFD_test"
        provider_refund_id = None

    intent = provider.query_refund(refund=StubRefund())

    assert intent.status == "SUCCESS"
    assert intent.provider_refund_id == "503000001"
