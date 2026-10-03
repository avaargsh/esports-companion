from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import User
from app.config import settings


def test_mock_wechat_login_contract_and_refresh_rotation():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-customer"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["userId"]
        assert body["provider"] == "MOCK"
        assert isinstance(body["isNewUser"], bool)
        assert body["tokenType"] == "Bearer"
        assert body["accessToken"]
        assert body["refreshToken"]
        assert body["roles"] == ["USER"]

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['accessToken']}"},
        )
        assert me.status_code == 200
        assert me.json()["userId"] == body["userId"]

        refreshed = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": body["refreshToken"]},
        )
        assert refreshed.status_code == 200
        next_tokens = refreshed.json()
        assert next_tokens["accessToken"] != body["accessToken"]
        assert next_tokens["refreshToken"] != body["refreshToken"]

        old_access = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['accessToken']}"},
        )
        assert old_access.status_code == 401
        assert old_access.json()["detail"] == "ACCESS_SESSION_REVOKED"

        old_refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": body["refreshToken"]},
        )
        assert old_refresh.status_code == 401
        assert old_refresh.json()["detail"] == "REFRESH_TOKEN_REUSED"

        rotated_access = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {next_tokens['accessToken']}"},
        )
        assert rotated_access.status_code == 401
        assert rotated_access.json()["detail"] == "ACCESS_SESSION_REVOKED"


def test_logout_revokes_current_session():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-player-1"},
        ).json()

        logout = client.post(
            "/api/v1/auth/logout",
            json={"refreshToken": login["refreshToken"]},
        )
        assert logout.status_code == 204

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login['accessToken']}"},
        )
        assert me.status_code == 401
        assert me.json()["detail"] == "ACCESS_SESSION_REVOKED"


def test_logout_with_stale_rotated_refresh_revokes_current_session():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-customer"},
        ).json()

        refreshed = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": login["refreshToken"]},
        )
        assert refreshed.status_code == 200
        current = refreshed.json()

        logout = client.post(
            "/api/v1/auth/logout",
            json={"refreshToken": login["refreshToken"]},
        )
        assert logout.status_code == 204

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {current['accessToken']}"},
        )
        assert me.status_code == 401
        assert me.json()["detail"] == "ACCESS_SESSION_REVOKED"


def test_session_management_lists_active_sessions_and_logout_all():
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-player-2"},
        )
        second = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-player-2"},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        first_tokens = first.json()
        second_tokens = second.json()

        sessions = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {second_tokens['accessToken']}"},
        )
        assert sessions.status_code == 200
        rows = sessions.json()
        assert len(rows) >= 2
        assert sum(1 for row in rows if row["current"]) == 1
        assert all(row["provider"] == "MOCK" for row in rows)
        assert all(row["sessionId"] for row in rows)
        assert all(row["createdAt"] for row in rows)
        assert all(row["expiresAt"] for row in rows)

        logout_all = client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {second_tokens['accessToken']}"},
        )
        assert logout_all.status_code == 204

        for token in (first_tokens["accessToken"], second_tokens["accessToken"]):
            me = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me.status_code == 401
            assert me.json()["detail"] == "ACCESS_SESSION_REVOKED"

def test_revoke_one_session_keeps_current_session_active():
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-player-3"},
        ).json()
        second = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-player-3"},
        ).json()

        first_sessions = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {first['accessToken']}"},
        )
        assert first_sessions.status_code == 200
        first_session_id = next(
            row["sessionId"]
            for row in first_sessions.json()
            if row["current"]
        )

        revoked = client.delete(
            f"/api/v1/auth/sessions/{first_session_id}",
            headers={"Authorization": f"Bearer {second['accessToken']}"},
        )
        assert revoked.status_code == 204

        first_me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {first['accessToken']}"},
        )
        assert first_me.status_code == 401
        assert first_me.json()["detail"] == "ACCESS_SESSION_REVOKED"

        second_me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {second['accessToken']}"},
        )
        assert second_me.status_code == 200


def test_cannot_revoke_another_users_session():
    with TestClient(app) as client:
        owner = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-customer"},
        ).json()
        attacker = client.post(
            "/api/v1/auth/wechat/login",
            json={"code": "demo-player-1"},
        ).json()

        owner_sessions = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {owner['accessToken']}"},
        )
        assert owner_sessions.status_code == 200
        owner_session_id = next(
            row["sessionId"]
            for row in owner_sessions.json()
            if row["current"]
        )

        denied = client.delete(
            f"/api/v1/auth/sessions/{owner_session_id}",
            headers={"Authorization": f"Bearer {attacker['accessToken']}"},
        )
        assert denied.status_code == 404
        assert denied.json()["detail"] == "SESSION_NOT_FOUND"

        owner_me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {owner['accessToken']}"},
        )
        assert owner_me.status_code == 200



def test_admin_wechat_login_requires_platform_role():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/wechat/admin-login",
            json={"code": "demo-customer"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_REQUIRED"


def test_admin_wechat_login_issues_platform_session():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.openid == "mock:platform"))
        if user is None:
            user = User(
                openid="mock:platform",
                nickname="Platform",
                role="PLATFORM",
                status="ACTIVE",
            )
            db.add(user)
        else:
            user.role = "PLATFORM"
            user.status = "ACTIVE"
        db.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/wechat/admin-login",
            json={"code": "demo-platform"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "MOCK"
    assert "PLATFORM" in body["roles"]
    assert body["tokenType"] == "Bearer"
    assert body["accessToken"]
    assert body["refreshToken"]


def test_admin_wechat_qr_config_returns_authorize_url(monkeypatch):
    monkeypatch.setattr(settings, "wechat_web_app_id", "web-app-id", raising=False)
    monkeypatch.setattr(settings, "wechat_web_app_secret", "web-secret", raising=False)
    monkeypatch.setattr(
        settings,
        "wechat_web_redirect_uri",
        "https://admin.example.com/wechat/callback",
        raising=False,
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/wechat/admin-qr")

    assert response.status_code == 200
    body = response.json()
    assert body["appId"] == "web-app-id"
    assert body["state"]
    assert "open.weixin.qq.com/connect/qrconnect" in body["authorizeUrl"]
    assert "scope=snsapi_login" in body["authorizeUrl"]


def test_admin_wechat_qr_login_requires_platform_union(monkeypatch):
    from app.routers import auth as auth_router
    from app.providers.auth import ExternalIdentity

    monkeypatch.setattr(settings, "wechat_web_app_id", "web-app-id", raising=False)
    monkeypatch.setattr(settings, "wechat_web_app_secret", "web-secret", raising=False)
    monkeypatch.setattr(
        settings,
        "wechat_web_redirect_uri",
        "https://admin.example.com/wechat/callback",
        raising=False,
    )
    monkeypatch.setattr(auth_router, "_verify_admin_qr_state", lambda state: None)

    class StubProvider:
        name = "WECHAT_WEB"

        def exchange_code(self, code):
            assert code == "web-code"
            return ExternalIdentity(
                provider="WECHAT_WEB",
                subject="web-openid-user",
                union_id="union-normal-user",
                provider_session_key="web-access-token",
            )

    monkeypatch.setattr(auth_router, "get_wechat_web_auth_provider", lambda: StubProvider())
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.unionid == "union-normal-user"))
        if user is None:
            user = User(
                openid="mini-openid-normal",
                unionid="union-normal-user",
                nickname="Normal",
                role="USER",
                status="ACTIVE",
            )
            db.add(user)
        else:
            user.role = "USER"
            user.status = "ACTIVE"
        db.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/wechat/admin-qr-login",
            json={"code": "web-code", "state": "state-ok-123456789"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_REQUIRED"


def test_admin_wechat_qr_login_issues_platform_session(monkeypatch):
    from app.routers import auth as auth_router
    from app.providers.auth import ExternalIdentity

    monkeypatch.setattr(settings, "wechat_web_app_id", "web-app-id", raising=False)
    monkeypatch.setattr(settings, "wechat_web_app_secret", "web-secret", raising=False)
    monkeypatch.setattr(
        settings,
        "wechat_web_redirect_uri",
        "https://admin.example.com/wechat/callback",
        raising=False,
    )
    monkeypatch.setattr(auth_router, "_verify_admin_qr_state", lambda state: None)

    class StubProvider:
        name = "WECHAT_WEB"

        def exchange_code(self, code):
            assert code == "web-code"
            return ExternalIdentity(
                provider="WECHAT_WEB",
                subject="web-openid-platform",
                union_id="union-platform-user",
                provider_session_key="web-access-token",
            )

    monkeypatch.setattr(auth_router, "get_wechat_web_auth_provider", lambda: StubProvider())
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.unionid == "union-platform-user"))
        if user is None:
            user = User(
                openid="mini-openid-platform",
                unionid="union-platform-user",
                nickname="Platform",
                role="PLATFORM",
                status="ACTIVE",
            )
            db.add(user)
        else:
            user.role = "PLATFORM"
            user.status = "ACTIVE"
        db.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/wechat/admin-qr-login",
            json={"code": "web-code", "state": "state-ok-123456789"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "WECHAT_WEB"
    assert "PLATFORM" in body["roles"]
    assert body["accessToken"]
    assert body["refreshToken"]
