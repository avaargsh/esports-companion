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
