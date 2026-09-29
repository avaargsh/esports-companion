import base64
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID

from app.providers.refund_callback import WeChatRefundCallbackVerifier


def _certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "wechat-refund-test")]
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


def _callback(event_type="REFUND.SUCCESS", refund_status="SUCCESS"):
    key, pem, serial = _certificate()
    api_key = "0123456789abcdef0123456789abcdef"
    payload = {
        "mchid": "mch-1",
        "transaction_id": "420000001",
        "out_trade_no": "ORD_TEST",
        "refund_id": "503000001",
        "out_refund_no": "RFD_test",
        "refund_status": refund_status,
        "amount": {
            "total": 3000,
            "refund": 3000,
            "payer_total": 3000,
            "payer_refund": 3000,
        },
    }
    nonce = "refund-nonce"
    associated = "refund"
    encrypted = AESGCM(api_key.encode()).encrypt(
        nonce.encode(),
        json.dumps(payload).encode(),
        associated.encode(),
    )
    event = {
        "id": "refund-event-1",
        "event_type": event_type,
        "resource_type": "encrypt-resource",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "original_type": "refund",
            "ciphertext": base64.b64encode(encrypted).decode(),
            "nonce": nonce,
            "associated_data": associated,
        },
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    header_nonce = "header-refund-nonce"
    message = timestamp.encode() + b"\n" + header_nonce.encode() + b"\n" + body + b"\n"
    signature = base64.b64encode(
        key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    headers = {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": header_nonce,
        "Wechatpay-Signature": signature,
        "Wechatpay-Serial": serial,
    }
    verifier = WeChatRefundCallbackVerifier(
        api_v3_key=api_key,
        platform_cert_serial=serial,
        platform_certificate=pem,
        expected_mch_id="mch-1",
    )
    return verifier, headers, body


def test_wechat_refund_callback_verifies_and_decrypts_success():
    verifier, headers, body = _callback()
    callback = verifier.verify_and_decrypt(headers=headers, body=body)

    assert callback.provider_refund_id == "503000001"
    assert callback.out_refund_no == "RFD_test"
    assert callback.provider_txn_id == "420000001"
    assert callback.refund_status == "SUCCESS"
    assert callback.total_amount == 3000
    assert callback.refund_amount == 3000


def test_wechat_refund_callback_rejects_tampered_body():
    verifier, headers, body = _callback()
    tampered = body.replace(b"refund-event-1", b"refund-event-X")

    with pytest.raises(ValueError, match="WECHAT_REFUND_CALLBACK_SIGNATURE_INVALID"):
        verifier.verify_and_decrypt(headers=headers, body=tampered)
