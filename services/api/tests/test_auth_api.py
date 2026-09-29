from fastapi.testclient import TestClient

from app.main import app


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
