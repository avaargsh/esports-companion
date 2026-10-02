import base64
import json
from dataclasses import dataclass
from typing import Any

import requests
from Crypto.Cipher import AES


@dataclass(frozen=True)
class WeChatSession:
    openid: str
    session_key: str
    unionid: str | None = None


class WeChatMiniProgramClient:
    CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        timeout_seconds: float = 5.0,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout_seconds = timeout_seconds

    def code2session(self, code: str) -> WeChatSession:
        if not self.app_id or not self.app_secret:
            raise ValueError("WECHAT_AUTH_CREDENTIALS_MISSING")
        if not code.strip():
            raise ValueError("WECHAT_LOGIN_CODE_REQUIRED")
        try:
            response = requests.get(
                self.CODE2SESSION_URL,
                params={
                    "appid": self.app_id,
                    "secret": self.app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ValueError("WECHAT_CODE2SESSION_REQUEST_FAILED") from exc
        except ValueError as exc:
            raise ValueError("WECHAT_CODE2SESSION_INVALID_JSON") from exc

        errcode = payload.get("errcode")
        if errcode not in (None, 0):
            raise ValueError(f"WECHAT_CODE2SESSION_FAILED:{errcode}")
        openid = payload.get("openid")
        session_key = payload.get("session_key")
        if not openid or not session_key:
            raise ValueError("WECHAT_CODE2SESSION_INVALID_RESPONSE")
        return WeChatSession(
            openid=str(openid),
            session_key=str(session_key),
            unionid=str(payload["unionid"]) if payload.get("unionid") else None,
        )


def decrypt_phone_number(
    *,
    encrypted_data: str,
    iv: str,
    session_key: str,
    expected_app_id: str,
) -> dict[str, Any]:
    try:
        cipher = AES.new(
            base64.b64decode(session_key),
            AES.MODE_CBC,
            base64.b64decode(iv),
        )
        raw = cipher.decrypt(base64.b64decode(encrypted_data))
        padding = raw[-1]
        if padding < 1 or padding > 16:
            raise ValueError("INVALID_PKCS7_PADDING")
        payload = json.loads(raw[:-padding].decode("utf-8"))
    except Exception as exc:
        raise ValueError("WECHAT_PHONE_DECRYPT_FAILED") from exc

    watermark = payload.get("watermark") or {}
    if expected_app_id and watermark.get("appid") != expected_app_id:
        raise ValueError("WECHAT_PHONE_APPID_MISMATCH")
    phone = payload.get("purePhoneNumber") or payload.get("phoneNumber")
    if not phone:
        raise ValueError("WECHAT_PHONE_MISSING")
    return payload
