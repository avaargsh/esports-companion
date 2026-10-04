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
    ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    PHONE_NUMBER_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"

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

    def get_access_token(self) -> str:
        if not self.app_id or not self.app_secret:
            raise ValueError("WECHAT_AUTH_CREDENTIALS_MISSING")
        try:
            response = requests.get(
                self.ACCESS_TOKEN_URL,
                params={
                    "appid": self.app_id,
                    "secret": self.app_secret,
                    "grant_type": "client_credential",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ValueError("WECHAT_ACCESS_TOKEN_REQUEST_FAILED") from exc
        except ValueError as exc:
            raise ValueError("WECHAT_ACCESS_TOKEN_INVALID_JSON") from exc

        errcode = payload.get("errcode")
        if errcode not in (None, 0):
            raise ValueError(f"WECHAT_ACCESS_TOKEN_FAILED:{errcode}")
        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError("WECHAT_ACCESS_TOKEN_INVALID_RESPONSE")
        return str(access_token)

    def get_phone_number(self, code: str) -> dict[str, Any]:
        if not code.strip():
            raise ValueError("WECHAT_PHONE_CODE_REQUIRED")
        access_token = self.get_access_token()
        try:
            response = requests.post(
                self.PHONE_NUMBER_URL,
                params={"access_token": access_token},
                json={"code": code},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ValueError("WECHAT_PHONE_REQUEST_FAILED") from exc
        except ValueError as exc:
            raise ValueError("WECHAT_PHONE_INVALID_JSON") from exc

        errcode = payload.get("errcode")
        if errcode not in (None, 0):
            raise ValueError(f"WECHAT_PHONE_FAILED:{errcode}")
        phone_info = payload.get("phone_info")
        if not isinstance(phone_info, dict):
            raise ValueError("WECHAT_PHONE_INVALID_RESPONSE")
        phone = phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber")
        if not phone:
            raise ValueError("WECHAT_PHONE_MISSING")
        return phone_info


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
