import base64
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.models import Order, PaymentTransaction, Refund


RefundStatus = Literal["PENDING", "PROCESSING", "SUCCESS", "CLOSED", "ABNORMAL"]


@dataclass(frozen=True)
class RefundIntent:
    provider: str
    provider_refund_id: str | None
    status: RefundStatus
    raw_payload: dict


class RefundProvider(Protocol):
    name: str

    def create_refund(
        self,
        *,
        refund: Refund,
        order: Order,
        payment: PaymentTransaction,
        reason: str,
    ) -> RefundIntent:
        """Create or replay a provider-side refund using a stable merchant refund id."""


class ManualRefundProvider:
    name = "MANUAL"

    def create_refund(
        self,
        *,
        refund: Refund,
        order: Order,
        payment: PaymentTransaction,
        reason: str,
    ) -> RefundIntent:
        return RefundIntent(
            provider=self.name,
            provider_refund_id=None,
            status="PENDING",
            raw_payload={"mode": "manual"},
        )


HttpTransport = Callable[[str, dict[str, str], bytes, float], tuple[int, dict]]


class WeChatRefundProvider:
    name = "WECHAT"
    REFUND_PATH = "/v3/refund/domestic/refunds"

    def __init__(
        self,
        *,
        mch_id: str,
        cert_serial: str,
        private_key: str,
        notify_url: str,
        api_base_url: str = "https://api.mch.weixin.qq.com",
        timeout_seconds: float = 8.0,
        transport: HttpTransport | None = None,
    ):
        required = {
            "WECHAT_MCH_ID": mch_id,
            "WECHAT_MCH_CERT_SERIAL": cert_serial,
            "WECHAT_MCH_PRIVATE_KEY": private_key,
            "WECHAT_REFUND_NOTIFY_URL": notify_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"WECHAT_REFUND_CREDENTIALS_MISSING:{','.join(missing)}")

        self.mch_id = mch_id
        self.cert_serial = cert_serial
        self.notify_url = notify_url
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._post_json
        self.private_key = self._load_private_key(private_key)

    def create_refund(
        self,
        *,
        refund: Refund,
        order: Order,
        payment: PaymentTransaction,
        reason: str,
    ) -> RefundIntent:
        if payment.provider.upper() != self.name or payment.status != "SUCCESS":
            raise ValueError("WECHAT_REFUND_REQUIRES_SUCCESSFUL_WECHAT_PAYMENT")
        if not payment.provider_txn_id:
            raise ValueError("WECHAT_PAYMENT_TRANSACTION_ID_MISSING")
        if not refund.out_refund_no:
            raise ValueError("REFUND_OUT_REFUND_NO_MISSING")

        request_body = {
            "transaction_id": payment.provider_txn_id,
            "out_refund_no": refund.out_refund_no,
            "reason": self._truncate_utf8(reason or "Dispute refund", 80),
            "notify_url": self.notify_url,
            "amount": {
                "refund": refund.amount,
                "total": order.total_amount,
                "currency": "CNY",
            },
        }
        body = json.dumps(request_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        authorization = self._authorization_header(
            method="POST",
            path=self.REFUND_PATH,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
        status, response = self.transport(
            f"{self.api_base_url}{self.REFUND_PATH}",
            {
                "Authorization": authorization,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "esports-companion/0.2",
            },
            body,
            self.timeout_seconds,
        )
        if status < 200 or status >= 300:
            code = response.get("code", "UNKNOWN")
            raise ValueError(f"WECHAT_REFUND_HTTP_ERROR:{status}:{code}")

        provider_refund_id = response.get("refund_id")
        out_refund_no = response.get("out_refund_no")
        refund_status = str(response.get("status") or "").upper()
        if not provider_refund_id or out_refund_no != refund.out_refund_no:
            raise ValueError("WECHAT_REFUND_INVALID_RESPONSE")
        if refund_status not in {"SUCCESS", "PROCESSING", "CLOSED", "ABNORMAL"}:
            raise ValueError("WECHAT_REFUND_STATUS_INVALID")

        return RefundIntent(
            provider=self.name,
            provider_refund_id=str(provider_refund_id),
            status=refund_status,
            raw_payload=response,
        )

    def _authorization_header(
        self,
        *,
        method: str,
        path: str,
        timestamp: str,
        nonce: str,
        body: bytes,
    ) -> str:
        message = (
            f"{method}\n{path}\n{timestamp}\n{nonce}\n"
        ).encode("utf-8") + body + b"\n"
        signature = self._sign(message)
        return (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{self.mch_id}",'
            f'nonce_str="{nonce}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self.cert_serial}"'
        )

    def _sign(self, message: bytes) -> str:
        signature = self.private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("ascii")

    @staticmethod
    def _load_private_key(value: str):
        material = value.replace("\\n", "\n").strip()
        if not material.startswith("-----BEGIN"):
            material = Path(material).read_text(encoding="utf-8")
        return serialization.load_pem_private_key(material.encode("utf-8"), password=None)

    @staticmethod
    def _truncate_utf8(value: str, limit: int) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= limit:
            return value
        encoded = encoded[:limit]
        while encoded:
            try:
                return encoded.decode("utf-8")
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        return ""

    @staticmethod
    def _post_json(
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, dict]:
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
                status = getattr(response, "status", 200)
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8") if exc.fp else "{}"
        except URLError as exc:
            raise ValueError("WECHAT_REFUND_NETWORK_ERROR") from exc

        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ValueError("WECHAT_REFUND_INVALID_JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("WECHAT_REFUND_INVALID_RESPONSE")
        return status, payload
