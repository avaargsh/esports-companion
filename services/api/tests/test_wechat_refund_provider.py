import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.providers.refund import WeChatRefundProvider


def _private_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_wechat_refund_provider_uses_stable_out_refund_no_and_original_transaction():
    captured = {}

    def transport(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=body, timeout=timeout)
        return 200, {
            "refund_id": "503000001",
            "out_refund_no": "RFD_test",
            "transaction_id": "420000001",
            "out_trade_no": "ORD_TEST",
            "status": "PROCESSING",
        }

    provider = WeChatRefundProvider(
        mch_id="mch-1",
        cert_serial="serial-1",
        private_key=_private_key_pem(),
        notify_url="https://example.com/api/v1/refunds/wechat/callback",
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
