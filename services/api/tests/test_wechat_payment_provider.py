import base64
import json
from decimal import Decimal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Game, PaymentTransaction, ServiceSKU, User
from app.providers.payment import WeChatPaymentProvider
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService


def _private_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return key, pem


def test_wechat_payment_creates_pending_prepay_and_signed_client_params():
    key, pem = _private_key_pem()
    captured = {}

    def transport(url, headers, body, timeout):
        captured.update(
            url=url,
            headers=headers,
            body=body,
            timeout=timeout,
        )
        return 200, {"prepay_id": "wx-prepay-123"}

    provider = WeChatPaymentProvider(
        app_id="wx-app",
        mch_id="mch-1",
        cert_serial="serial-1",
        private_key=pem,
        notify_url="https://example.com/api/v1/payments/wechat/callback",
        transport=transport,
    )

    class StubOrder:
        order_no = "ORD_TEST_1"
        total_amount = 3000

    intent = provider.create_payment(
        order=StubOrder(),
        idempotency_key="idem-1",
        payer_subject="openid-1",
    )

    assert captured["url"].endswith("/v3/pay/transactions/jsapi")
    request = json.loads(captured["body"])
    assert request["appid"] == "wx-app"
    assert request["mchid"] == "mch-1"
    assert request["out_trade_no"] == "ORD_TEST_1"
    assert request["amount"] == {"total": 3000, "currency": "CNY"}
    assert request["payer"] == {"openid": "openid-1"}
    assert captured["headers"]["Authorization"].startswith(
        "WECHATPAY2-SHA256-RSA2048 "
    )

    assert intent.status == "PENDING"
    assert intent.provider_txn_id == "wx-prepay-123"
    assert intent.client_payload["package"] == "prepay_id=wx-prepay-123"
    assert intent.client_payload["signType"] == "RSA"

    client_message = (
        "wx-app\n"
        f"{intent.client_payload['timeStamp']}\n"
        f"{intent.client_payload['nonceStr']}\n"
        f"{intent.client_payload['package']}\n"
    ).encode("utf-8")
    key.public_key().verify(
        base64.b64decode(intent.client_payload["paySign"]),
        client_message,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_payment_service_keeps_wechat_order_waiting_until_callback_and_replays():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    _key, pem = _private_key_pem()
    calls = {"count": 0}

    def transport(_url, _headers, _body, _timeout):
        calls["count"] += 1
        return 200, {"prepay_id": "wx-prepay-idempotent"}

    provider = WeChatPaymentProvider(
        app_id="wx-app",
        mch_id="mch-1",
        cert_serial="serial-1",
        private_key=pem,
        notify_url="https://example.com/callback",
        transport=transport,
    )

    with Session() as db:
        customer = User(openid="openid-1", nickname="wechat-customer")
        game = Game(code="wechat-pay", name="WeChat Pay")
        db.add_all([customer, game])
        db.flush()
        sku = ServiceSKU(
            game_id=game.id,
            name="WeChat Pay SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate=Decimal("0.2000"),
        )
        db.add(sku)
        db.commit()

        order = OrderService.create_order(
            db,
            user_id=customer.id,
            sku_id=sku.id,
        )

        first = PaymentService.prepare_payment(
            db,
            order=order,
            provider=provider,
            idempotency_key="wechat-idem",
        )
        second = PaymentService.prepare_payment(
            db,
            order=order,
            provider=provider,
            idempotency_key="wechat-idem",
        )

        assert order.status == "WAITING_PAYMENT"
        assert first.transaction.status == "PENDING"
        assert second.replayed is True
        assert first.client_payload == second.client_payload
        assert calls["count"] == 1
        assert db.scalar(
            select(func.count()).select_from(PaymentTransaction)
        ) == 1
