import base64
from dataclasses import replace
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Game, OrderEvent, PaymentTransaction, ServiceSKU, User
from app.providers.payment import PaymentIntent
from app.providers.payment_callback import (
    VerifiedPaymentCallback,
    WeChatPaymentCallbackVerifier,
)
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService


def _certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "wechat-platform-test")]
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
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    serial = format(cert.serial_number, "X")
    return key, cert, pem, serial


def _signed_callback():
    key, _cert, pem, serial = _certificate()
    api_key = "0123456789abcdef0123456789abcdef"
    resource_payload = {
        "mchid": "mch-1",
        "appid": "wx-app",
        "out_trade_no": "ORD_CALLBACK",
        "transaction_id": "wx-txn-1",
        "trade_state": "SUCCESS",
        "payer": {"openid": "openid-1"},
        "amount": {"total": 3000, "currency": "CNY"},
    }
    nonce = "callback-nonce"
    associated = "transaction"
    encrypted = AESGCM(api_key.encode()).encrypt(
        nonce.encode(),
        json.dumps(resource_payload).encode(),
        associated.encode(),
    )
    event = {
        "id": "event-1",
        "event_type": "TRANSACTION.SUCCESS",
        "resource_type": "encrypt-resource",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": base64.b64encode(encrypted).decode(),
            "nonce": nonce,
            "associated_data": associated,
        },
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    header_nonce = "header-nonce"
    message = (
        timestamp.encode()
        + b"\n"
        + header_nonce.encode()
        + b"\n"
        + body
        + b"\n"
    )
    signature = base64.b64encode(
        key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    headers = {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": header_nonce,
        "Wechatpay-Signature": signature,
        "Wechatpay-Serial": serial,
    }
    verifier = WeChatPaymentCallbackVerifier(
        api_v3_key=api_key,
        platform_cert_serial=serial,
        platform_certificate=pem,
        expected_app_id="wx-app",
        expected_mch_id="mch-1",
    )
    return verifier, headers, body


def test_wechat_callback_verifies_signature_and_decrypts_resource():
    verifier, headers, body = _signed_callback()
    result = verifier.verify_and_decrypt(headers=headers, body=body)

    assert result.provider == "WECHAT"
    assert result.provider_txn_id == "wx-txn-1"
    assert result.out_trade_no == "ORD_CALLBACK"
    assert result.amount == 3000
    assert result.payer_subject == "openid-1"


def test_wechat_callback_rejects_tampered_body():
    verifier, headers, body = _signed_callback()
    tampered = body.replace(b"event-1", b"event-X")

    with pytest.raises(ValueError, match="WECHAT_CALLBACK_SIGNATURE_INVALID"):
        verifier.verify_and_decrypt(headers=headers, body=tampered)


class PendingProvider:
    name = "WECHAT"

    def create_payment(self, *, order, idempotency_key, payer_subject=None):
        return PaymentIntent(
            provider="WECHAT",
            # Exercise recovery where a pending row already carries the final
            # provider transaction id. It must not be mistaken for a replay.
            provider_txn_id="wx-txn-1",
            status="PENDING",
            raw_payload={"prepayId": "prepay-1"},
            client_payload={"package": "prepay_id=prepay-1"},
        )


def test_verified_callback_completes_pending_transaction_idempotently():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        customer = User(openid="openid-1", nickname="callback-customer")
        game = Game(code="callback-game", name="Callback")
        db.add_all([customer, game])
        db.flush()
        sku = ServiceSKU(
            game_id=game.id,
            name="Callback SKU",
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
        order.order_no = "ORD_CALLBACK"
        db.commit()

        PaymentService.prepare_payment(
            db,
            order=order,
            provider=PendingProvider(),
            idempotency_key="callback-idem",
        )
        assert order.status == "WAITING_PAYMENT"

        callback = VerifiedPaymentCallback(
            provider="WECHAT",
            provider_txn_id="wx-txn-1",
            out_trade_no="ORD_CALLBACK",
            amount=3000,
            currency="CNY",
            payer_subject="openid-1",
            raw_event={"id": "event-1"},
            resource={"transaction_id": "wx-txn-1"},
        )
        with pytest.raises(ValueError, match="PAYMENT_CURRENCY_MISMATCH"):
            PaymentService.apply_verified_success(
                db,
                callback=replace(callback, currency="USD"),
            )

        with pytest.raises(ValueError, match="PAYMENT_PAYER_MISMATCH"):
            PaymentService.apply_verified_success(
                db,
                callback=replace(callback, payer_subject="openid-other"),
            )

        first = PaymentService.apply_verified_success(
            db,
            callback=callback,
        )
        second = PaymentService.apply_verified_success(
            db,
            callback=callback,
        )

        assert first.order.status == "MATCHING"
        assert second.replayed is True
        assert db.scalar(
            select(func.count()).select_from(PaymentTransaction)
        ) == 1
        tx = db.scalar(select(PaymentTransaction))
        assert tx.status == "SUCCESS"
        assert tx.provider_txn_id == "wx-txn-1"
        assert db.scalar(select(func.count()).select_from(OrderEvent)) == 3
