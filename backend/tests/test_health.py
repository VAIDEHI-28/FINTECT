from fastapi.testclient import TestClient

from fintect.main import app

client = TestClient(app)


def test_health_endpoint_returns_healthy() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
