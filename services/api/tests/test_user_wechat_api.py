import base64
import json

from Crypto.Cipher import AES
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import AuthSession, User
from app.routers import user_wechat


class StubWeChatClient:
    def code2session(self, code: str):
        assert code == "wx-code"
        return user_wechat.WeChatSession(
            openid="openid-test-user",
            session_key=SESSION_KEY,
            unionid="union-test-user",
        )


SESSION_KEY = base64.b64encode(b"0123456789abcdef").decode("ascii")


def encrypted_phone_payload(phone: str) -> tuple[str, str]:
    iv = b"abcdef0123456789"
    data = json.dumps(
        {
            "phoneNumber": phone,
            "purePhoneNumber": phone,
            "countryCode": "86",
            "watermark": {"appid": settings.wechat_app_id},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    padding = 16 - len(data) % 16
    plain = data + bytes([padding]) * padding
    cipher = AES.new(base64.b64decode(SESSION_KEY), AES.MODE_CBC, iv)
    encrypted = base64.b64encode(cipher.encrypt(plain)).decode("ascii")
    return encrypted, base64.b64encode(iv).decode("ascii")


def override_wechat_client():
    app.dependency_overrides[user_wechat.get_wechat_client] = lambda: StubWeChatClient()


def clear_overrides():
    app.dependency_overrides.clear()


def test_wx_login_creates_user_session_and_returns_standard_json():
    override_wechat_client()
    try:
        with TestClient(app) as client:
            response = client.post("/api/user/wx-login", json={"code": "wx-code"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    data = body["data"]
    assert data["openid"] == "openid-test-user"
    assert data["tokenType"] == "Bearer"
    assert data["token"]
    assert data["accessToken"] == data["token"]
    assert data["refreshToken"]

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.openid == "openid-test-user"))
        assert user is not None
        assert user.unionid == "union-test-user"
        session = db.scalar(
            select(AuthSession)
            .where(AuthSession.user_id == user.id)
            .order_by(AuthSession.created_at.desc())
        )
        assert session is not None
        assert session.provider_session_key == SESSION_KEY


def test_bind_phone_decrypts_wechat_phone_and_updates_current_user():
    override_wechat_client()
    encrypted_data, iv = encrypted_phone_payload("13800138000")
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/user/wx-login",
                json={"code": "wx-code"},
            ).json()["data"]
            response = client.post(
                "/api/user/bind-phone",
                headers={"Authorization": f"Bearer {login['token']}"},
                json={"encryptedData": encrypted_data, "iv": iv},
            )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"phone": "13800138000", "bound": True},
    }

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.openid == "openid-test-user"))
        assert user.phone == "13800138000"


def test_bind_phone_requires_wechat_session_key():
    override_wechat_client()
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/user/wx-login",
                json={"code": "wx-code"},
            ).json()["data"]
            with SessionLocal() as db:
                session = db.scalar(
                    select(AuthSession)
                    .where(AuthSession.user_id == login["userId"])
                    .order_by(AuthSession.created_at.desc())
                )
                session.provider_session_key = None
                db.commit()
            response = client.post(
                "/api/user/bind-phone",
                headers={"Authorization": f"Bearer {login['accessToken']}"},
                json={"encryptedData": "bad", "iv": "bad"},
            )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json() == {
        "code": 1,
        "message": "WECHAT_SESSION_KEY_MISSING",
        "data": None,
    }


def test_current_user_profile_can_be_read_and_updated():
    override_wechat_client()
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/user/wx-login",
                json={"code": "wx-code"},
            ).json()["data"]
            headers = {"Authorization": f"Bearer {login['token']}"}

            initial = client.get("/api/user/me", headers=headers)
            assert initial.status_code == 200
            assert initial.json()["data"]["userId"] == login["userId"]

            updated = client.patch(
                "/api/user/profile",
                headers=headers,
                json={
                    "nickname": "真实微信昵称",
                    "avatarUrl": "http://localhost:9000/esports-images/avatar.png",
                },
            )
            assert updated.status_code == 200
            assert updated.json()["data"]["nickname"] == "真实微信昵称"
            assert updated.json()["data"]["avatarUrl"].endswith("avatar.png")

            current = client.get("/api/user/me", headers=headers)
            assert current.json()["data"]["nickname"] == "真实微信昵称"
    finally:
        clear_overrides()


def test_user_avatar_upload_stores_image_and_returns_url(monkeypatch):
    class StubStorage:
        def upload_image_bytes(self, *, filename, content, content_type):
            assert filename == "avatar.png"
            assert content == b"avatar-bytes"
            assert content_type == "image/png"
            return "images/avatar.png"

        def get_public_url(self, key):
            assert key == "images/avatar.png"
            return "http://localhost:9000/esports-images/images/avatar.png"

    monkeypatch.setattr(user_wechat, "_storage", lambda: StubStorage())
    override_wechat_client()
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/user/wx-login",
                json={"code": "wx-code"},
            ).json()["data"]
            response = client.post(
                "/api/user/avatar",
                headers={"Authorization": f"Bearer {login['token']}"},
                json={
                    "filename": "avatar.png",
                    "contentType": "image/png",
                    "dataBase64": base64.b64encode(b"avatar-bytes").decode("ascii"),
                },
            )
    finally:
        clear_overrides()

    assert response.status_code == 201
    assert response.json()["data"] == {
        "key": "images/avatar.png",
        "url": "http://localhost:9000/esports-images/images/avatar.png",
    }
