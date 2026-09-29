from fastapi.testclient import TestClient

from app.main import app


def test_liveness_and_readiness_contract():
    with TestClient(app) as client:
        live = client.get("/livez")
        assert live.status_code == 200
        assert live.json()["status"] == "alive"
        assert live.headers["X-Request-Id"]

        ready = client.get("/readyz")
        assert ready.status_code == 200
        body = ready.json()
        assert body["status"] == "ready"
        assert body["dependencies"]["postgres"] is True
        assert body["dependencies"]["redis"] is True


def test_health_compatibility_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
