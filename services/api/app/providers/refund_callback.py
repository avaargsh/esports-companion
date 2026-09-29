import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class VerifiedRefundCallback:
    provider: str
    provider_refund_id: str
    out_refund_no: str
    provider_txn_id: str
    out_trade_no: str
    refund_status: str
    total_amount: int
    refund_amount: int
    raw_event: dict
    resource: dict


Clock = Callable[[], float]


class WeChatRefundCallbackVerifier:
    name = "WECHAT"

    def __init__(
        self,
        *,
        api_v3_key: str,
        platform_cert_serial: str,
        platform_certificate: str,
        expected_mch_id: str,
        max_timestamp_skew_seconds: int = 300,
        clock: Clock | None = None,
    ):
        if len(api_v3_key.encode("utf-8")) != 32:
            raise ValueError("WECHAT_PAY_API_V3_KEY_MUST_BE_32_BYTES")
        required = {
            "WECHAT_PAY_PLATFORM_CERT_SERIAL": platform_cert_serial,
            "WECHAT_PAY_PLATFORM_CERTIFICATE": platform_certificate,
            "WECHAT_MCH_ID": expected_mch_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"WECHAT_REFUND_CALLBACK_CONFIG_MISSING:{','.join(missing)}")

        self.api_v3_key = api_v3_key.encode("utf-8")
        self.platform_cert_serial = self._normalize_serial(platform_cert_serial)
        self.certificate = self._load_certificate(platform_certificate)
        self.expected_mch_id = expected_mch_id
        self.max_timestamp_skew_seconds = max_timestamp_skew_seconds
        self.clock = clock or time.time

    def verify_and_decrypt(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedRefundCallback:
        lowered = {key.lower(): value for key, value in headers.items()}
        timestamp = lowered.get("wechatpay-timestamp")
        nonce = lowered.get("wechatpay-nonce")
        signature = lowered.get("wechatpay-signature")
        serial = lowered.get("wechatpay-serial")

        if not timestamp or not nonce or not signature or not serial:
            raise ValueError("WECHAT_REFUND_CALLBACK_HEADERS_MISSING")
        if self._normalize_serial(serial) != self.platform_cert_serial:
            raise ValueError("WECHAT_REFUND_CALLBACK_CERT_SERIAL_UNKNOWN")

        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise ValueError("WECHAT_REFUND_CALLBACK_TIMESTAMP_INVALID") from exc
        if abs(int(self.clock()) - timestamp_int) > self.max_timestamp_skew_seconds:
            raise ValueError("WECHAT_REFUND_CALLBACK_TIMESTAMP_EXPIRED")

        message = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body + b"\n"
        try:
            self.certificate.public_key().verify(
                base64.b64decode(signature),
                message,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("WECHAT_REFUND_CALLBACK_SIGNATURE_INVALID") from exc

        try:
            event = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("WECHAT_REFUND_CALLBACK_INVALID_JSON") from exc
        if not isinstance(event, dict):
            raise ValueError("WECHAT_REFUND_CALLBACK_INVALID_JSON")

        event_type = str(event.get("event_type") or "")
        if event_type not in {"REFUND.SUCCESS", "REFUND.ABNORMAL", "REFUND.CLOSED"}:
            raise ValueError("WECHAT_REFUND_CALLBACK_EVENT_UNSUPPORTED")

        resource = event.get("resource")
        if not isinstance(resource, dict):
            raise ValueError("WECHAT_REFUND_CALLBACK_RESOURCE_MISSING")
        if resource.get("algorithm") != "AEAD_AES_256_GCM":
            raise ValueError("WECHAT_REFUND_CALLBACK_ALGORITHM_UNSUPPORTED")
        if resource.get("original_type") not in {None, "refund"}:
            raise ValueError("WECHAT_REFUND_CALLBACK_RESOURCE_TYPE_INVALID")

        try:
            ciphertext = base64.b64decode(resource["ciphertext"])
            resource_nonce = str(resource["nonce"]).encode("utf-8")
        except (KeyError, ValueError) as exc:
            raise ValueError("WECHAT_REFUND_CALLBACK_RESOURCE_INVALID") from exc
        associated_data = str(resource.get("associated_data") or "").encode("utf-8")

        try:
            plaintext = AESGCM(self.api_v3_key).decrypt(
                resource_nonce,
                ciphertext,
                associated_data,
            )
            payload = json.loads(plaintext)
        except Exception as exc:
            raise ValueError("WECHAT_REFUND_CALLBACK_DECRYPT_FAILED") from exc
        if not isinstance(payload, dict):
            raise ValueError("WECHAT_REFUND_CALLBACK_RESOURCE_INVALID")
        if payload.get("mchid") != self.expected_mch_id:
            raise ValueError("WECHAT_REFUND_CALLBACK_MCHID_MISMATCH")

        refund_status = str(payload.get("refund_status") or "").upper()
        expected_status = {
            "REFUND.SUCCESS": "SUCCESS",
            "REFUND.ABNORMAL": "ABNORMAL",
            "REFUND.CLOSED": "CLOSED",
        }[event_type]
        if refund_status != expected_status:
            raise ValueError("WECHAT_REFUND_CALLBACK_STATUS_MISMATCH")

        amount = payload.get("amount")
        if (
            not isinstance(amount, dict)
            or not isinstance(amount.get("total"), int)
            or not isinstance(amount.get("refund"), int)
        ):
            raise ValueError("WECHAT_REFUND_CALLBACK_AMOUNT_INVALID")

        refund_id = payload.get("refund_id")
        out_refund_no = payload.get("out_refund_no")
        transaction_id = payload.get("transaction_id")
        out_trade_no = payload.get("out_trade_no")
        if not all([refund_id, out_refund_no, transaction_id, out_trade_no]):
            raise ValueError("WECHAT_REFUND_CALLBACK_IDENTIFIERS_MISSING")

        return VerifiedRefundCallback(
            provider=self.name,
            provider_refund_id=str(refund_id),
            out_refund_no=str(out_refund_no),
            provider_txn_id=str(transaction_id),
            out_trade_no=str(out_trade_no),
            refund_status=refund_status,
            total_amount=amount["total"],
            refund_amount=amount["refund"],
            raw_event=event,
            resource=payload,
        )

    @staticmethod
    def _normalize_serial(value: str) -> str:
        normalized = value.strip().upper().lstrip("0")
        return normalized or "0"

    @staticmethod
    def _load_certificate(value: str):
        material = value.replace("\\n", "\n").strip()
        if not material.startswith("-----BEGIN"):
            material = Path(material).read_text(encoding="utf-8")
        return x509.load_pem_x509_certificate(material.encode("utf-8"))
