from fastapi.testclient import TestClient

from app.main import app


def test_demo_bootstrap_returns_seeded_identities():
    client = TestClient(app)
    response = client.get("/api/v1/dev/bootstrap")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo"
    assert body["customerUserId"]
    assert body["playerUserId"]
    assert body["adminUserId"]
    assert body["games"]
