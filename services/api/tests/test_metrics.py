from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_records_stable_route_templates():
    with TestClient(app) as client:
        assert client.get("/livez").status_code == 200
        assert client.get("/not-a-real-route/123456").status_code == 404

        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text

        assert "esports_http_requests_total" in body
        assert 'route="/livez"' in body
        assert 'route="unmatched"' in body
        assert "/not-a-real-route/123456" not in body
        assert "esports_http_request_duration_seconds_bucket" in body


def test_order_transition_metric_is_exposed():
    with TestClient(app) as client:
        bootstrap = client.get("/api/v1/dev/bootstrap").json()
        customer_id = bootstrap["customerUserId"]
        sku_id = bootstrap["games"][0]["skus"][0]["id"]

        created = client.post(
            "/api/v1/orders",
            headers={"X-User-Id": customer_id},
            json={"sku_id": sku_id, "quantity": 1, "remark": "metrics"},
        )
        assert created.status_code == 201

        response = client.get("/metrics")
        assert response.status_code == 200
        assert "esports_order_transitions_total" in response.text
