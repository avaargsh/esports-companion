from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.providers.auth import MockAuthProvider, WeChatAuthProvider, WeChatWebAuthProvider
from app.services.auth_service import AuthService


def test_mock_auth_maps_external_subject_to_stable_internal_user():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        provider = MockAuthProvider()

        first, first_created = AuthService.login_with_code(
            db,
            provider=provider,
            code="demo-customer",
        )
        second, second_created = AuthService.login_with_code(
            db,
            provider=provider,
            code="demo-customer",
        )

        assert first.id == second.id
        assert first.openid == "mock:customer"
        assert first_created is True
        assert second_created is False


def test_wechat_auth_exchanges_code_for_provider_session_and_identity():
    captured = {}

    def transport(url: str, timeout: float) -> dict:
        captured["url"] = url
        captured["timeout"] = timeout
        return {
            "openid": "openid-123",
            "session_key": "session-key-456",
            "unionid": "union-789",
        }

    provider = WeChatAuthProvider(
        app_id="wx-app-id",
        app_secret="wx-secret",
        transport=transport,
    )
    identity = provider.exchange_code("login-code")

    query = parse_qs(urlparse(captured["url"]).query)
    assert query["appid"] == ["wx-app-id"]
    assert query["secret"] == ["wx-secret"]
    assert query["js_code"] == ["login-code"]
    assert query["grant_type"] == ["authorization_code"]
    assert captured["timeout"] == 5.0
    assert identity.provider == "WECHAT"
    assert identity.subject == "openid-123"
    assert identity.union_id == "union-789"
    assert identity.provider_session_key == "session-key-456"


def test_wechat_auth_rejects_provider_error_response():
    provider = WeChatAuthProvider(
        app_id="wx-app-id",
        app_secret="wx-secret",
        transport=lambda _url, _timeout: {
            "errcode": 40029,
            "errmsg": "invalid code",
        },
    )

    with pytest.raises(ValueError, match="WECHAT_CODE_EXCHANGE_FAILED:40029"):
        provider.exchange_code("bad-code")


def test_wechat_auth_rejects_missing_session_fields():
    provider = WeChatAuthProvider(
        app_id="wx-app-id",
        app_secret="wx-secret",
        transport=lambda _url, _timeout: {"openid": "only-openid"},
    )

    with pytest.raises(ValueError, match="WECHAT_CODE_EXCHANGE_INVALID_RESPONSE"):
        provider.exchange_code("code")


def test_wechat_web_auth_builds_qr_authorize_url():
    provider = WeChatWebAuthProvider(
        app_id="web-app-id",
        app_secret="web-secret",
        redirect_uri="https://admin.example.com/wechat/callback",
    )

    url = provider.authorize_url("state-123")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "open.weixin.qq.com"
    assert parsed.path == "/connect/qrconnect"
    assert query["appid"] == ["web-app-id"]
    assert query["redirect_uri"] == ["https://admin.example.com/wechat/callback"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["snsapi_login"]
    assert query["state"] == ["state-123"]
    assert url.endswith("#wechat_redirect")


def test_wechat_web_auth_exchanges_code_for_union_identity():
    captured = {}

    def transport(url: str, timeout: float) -> dict:
        captured["url"] = url
        captured["timeout"] = timeout
        return {
            "openid": "web-openid-123",
            "access_token": "web-access-token",
            "refresh_token": "web-refresh-token",
            "unionid": "union-789",
        }

    provider = WeChatWebAuthProvider(
        app_id="web-app-id",
        app_secret="web-secret",
        redirect_uri="https://admin.example.com/wechat/callback",
        transport=transport,
    )
    identity = provider.exchange_code("web-code")

    query = parse_qs(urlparse(captured["url"]).query)
    assert query["appid"] == ["web-app-id"]
    assert query["secret"] == ["web-secret"]
    assert query["code"] == ["web-code"]
    assert query["grant_type"] == ["authorization_code"]
    assert identity.provider == "WECHAT_WEB"
    assert identity.subject == "web-openid-123"
    assert identity.union_id == "union-789"
    assert identity.provider_session_key == "web-access-token"
