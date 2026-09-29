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

from app.models import Order


PaymentStatus = Literal["PENDING", "SUCCESS"]


@dataclass(frozen=True)
class PaymentIntent:
    provider: str
    provider_txn_id: str
    status: PaymentStatus
    raw_payload: dict
    client_payload: dict


class PaymentProvider(Protocol):
    name: str

    def create_payment(
        self,
        *,
        order: Order,
        idempotency_key: str,
        payer_subject: str | None = None,
    ) -> PaymentIntent:
        """Create a provider-side payment attempt.

        The provider creates external payment state and returns client-side
        parameters when required. It must not transition the marketplace order.
        """


class MockPaymentProvider:
    name = "MOCK"

    def create_payment(
        self,
        *,
        order: Order,
        idempotency_key: str,
        payer_subject: str | None = None,
    ) -> PaymentIntent:
        return PaymentIntent(
            provider=self.name,
            provider_txn_id=f"mock_{uuid.uuid4().hex}",
            status="SUCCESS",
            raw_payload={
                "mode": "mock",
                "idempotencyKey": idempotency_key,
            },
            client_payload={},
        )


HttpTransport = Callable[[str, dict[str, str], bytes, float], tuple[int, dict]]


class WeChatPaymentProvider:
    name = "WECHAT"
    JSAPI_PATH = "/v3/pay/transactions/jsapi"

    def __init__(
        self,
        *,
        app_id: str,
        mch_id: str,
        cert_serial: str,
        private_key: str,
        notify_url: str,
        api_base_url: str = "https://api.mch.weixin.qq.com",
        timeout_seconds: float = 8.0,
        transport: HttpTransport | None = None,
    ):
        required = {
            "WECHAT_APP_ID": app_id,
            "WECHAT_MCH_ID": mch_id,
            "WECHAT_MCH_CERT_SERIAL": cert_serial,
            "WECHAT_MCH_PRIVATE_KEY": private_key,
            "WECHAT_NOTIFY_URL": notify_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"WECHAT_PAYMENT_CREDENTIALS_MISSING:{','.join(missing)}")

        self.app_id = app_id
        self.mch_id = mch_id
        self.cert_serial = cert_serial
        self.notify_url = notify_url
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._post_json
        self.private_key = self._load_private_key(private_key)

    def create_payment(
        self,
        *,
        order: Order,
        idempotency_key: str,
        payer_subject: str | None = None,
    ) -> PaymentIntent:
        if not payer_subject:
            raise ValueError("WECHAT_PAYER_OPENID_REQUIRED")

        request_body = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": f"Esports Companion {order.order_no}",
            "out_trade_no": order.order_no,
            "notify_url": self.notify_url,
            "amount": {
                "total": order.total_amount,
                "currency": "CNY",
            },
            "payer": {
                "openid": payer_subject,
            },
        }
        body = json.dumps(
            request_body,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        authorization = self._authorization_header(
            method="POST",
            path=self.JSAPI_PATH,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )

        status, response = self.transport(
            f"{self.api_base_url}{self.JSAPI_PATH}",
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
            raise ValueError(f"WECHAT_PAYMENT_HTTP_ERROR:{status}:{code}")

        prepay_id = response.get("prepay_id")
        if not prepay_id:
            raise ValueError("WECHAT_PAYMENT_INVALID_RESPONSE")

        client_timestamp = str(int(time.time()))
        client_nonce = uuid.uuid4().hex
        package = f"prepay_id={prepay_id}"
        client_message = (
            f"{self.app_id}\n{client_timestamp}\n{client_nonce}\n{package}\n"
        ).encode("utf-8")
        pay_sign = self._sign(client_message)

        return PaymentIntent(
            provider=self.name,
            provider_txn_id=str(prepay_id),
            status="PENDING",
            raw_payload={
                "outTradeNo": order.order_no,
                "prepayId": str(prepay_id),
                "providerResponse": response,
            },
            client_payload={
                "timeStamp": client_timestamp,
                "nonceStr": client_nonce,
                "package": package,
                "signType": "RSA",
                "paySign": pay_sign,
            },
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
        signature = self.private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("ascii")

    @staticmethod
    def _load_private_key(value: str):
        material = value.replace("\\n", "\n").strip()
        if not material.startswith("-----BEGIN"):
            material = Path(material).read_text(encoding="utf-8")
        return serialization.load_pem_private_key(
            material.encode("utf-8"),
            password=None,
        )

    @staticmethod
    def _post_json(
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, dict]:
        request = Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
                status = getattr(response, "status", 200)
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8") if exc.fp else "{}"
        except URLError as exc:
            raise ValueError("WECHAT_PAYMENT_NETWORK_ERROR") from exc

        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ValueError("WECHAT_PAYMENT_INVALID_JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("WECHAT_PAYMENT_INVALID_RESPONSE")
        return status, payload
