import json
from dataclasses import dataclass, field
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(frozen=True)
class ExternalIdentity:
    provider: str
    subject: str
    union_id: str | None = None
    nickname: str = ""
    provider_session_key: str | None = field(default=None, repr=False)


class AuthProvider(Protocol):
    name: str

    def exchange_code(self, code: str) -> ExternalIdentity:
        """Exchange an external login code for a provider-verified identity."""


class MockAuthProvider:
    name = "MOCK"

    _IDENTITIES = {
        "demo-customer": ExternalIdentity(
            provider="MOCK",
            subject="mock:customer",
            nickname="Demo Customer",
            provider_session_key="mock-session:customer",
        ),
        "demo-player-1": ExternalIdentity(
            provider="MOCK",
            subject="mock:player:1",
            nickname="Demo Player 1",
            provider_session_key="mock-session:player:1",
        ),
        "demo-player-2": ExternalIdentity(
            provider="MOCK",
            subject="mock:player:2",
            nickname="Demo Player 2",
            provider_session_key="mock-session:player:2",
        ),
        "demo-player-3": ExternalIdentity(
            provider="MOCK",
            subject="mock:player:3",
            nickname="Demo Player 3",
            provider_session_key="mock-session:player:3",
        ),
    }

    def exchange_code(self, code: str) -> ExternalIdentity:
        identity = self._IDENTITIES.get(code)
        if not identity:
            raise ValueError("INVALID_MOCK_LOGIN_CODE")
        return identity


JsonTransport = Callable[[str, float], dict]


class WeChatAuthProvider:
    name = "WECHAT"
    CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        timeout_seconds: float = 5.0,
        transport: JsonTransport | None = None,
    ):
        if not app_id or not app_secret:
            raise ValueError("WECHAT_AUTH_CREDENTIALS_MISSING")
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._fetch_json

    def exchange_code(self, code: str) -> ExternalIdentity:
        if not code.strip():
            raise ValueError("WECHAT_LOGIN_CODE_REQUIRED")

        query = urlencode(
            {
                "appid": self.app_id,
                "secret": self.app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            }
        )
        payload = self.transport(
            f"{self.CODE2SESSION_URL}?{query}",
            self.timeout_seconds,
        )

        errcode = payload.get("errcode")
        if errcode not in (None, 0):
            raise ValueError(f"WECHAT_CODE_EXCHANGE_FAILED:{errcode}")

        openid = payload.get("openid")
        session_key = payload.get("session_key")
        if not openid or not session_key:
            raise ValueError("WECHAT_CODE_EXCHANGE_INVALID_RESPONSE")

        return ExternalIdentity(
            provider=self.name,
            subject=str(openid),
            union_id=str(payload["unionid"]) if payload.get("unionid") else None,
            provider_session_key=str(session_key),
        )

    @staticmethod
    def _fetch_json(url: str, timeout_seconds: float) -> dict:
        try:
            with urlopen(url, timeout=timeout_seconds) as response:  # nosec B310
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise ValueError(f"WECHAT_CODE_EXCHANGE_HTTP_ERROR:{status}")
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise ValueError(f"WECHAT_CODE_EXCHANGE_HTTP_ERROR:{exc.code}") from exc
        except URLError as exc:
            raise ValueError("WECHAT_CODE_EXCHANGE_NETWORK_ERROR") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("WECHAT_CODE_EXCHANGE_INVALID_JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("WECHAT_CODE_EXCHANGE_INVALID_RESPONSE")
        return payload
