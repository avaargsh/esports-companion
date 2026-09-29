from fastapi.testclient import TestClient

from app.main import app


def test_mock_wechat_login_contract():
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
