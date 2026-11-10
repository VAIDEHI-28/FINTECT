import base64

import httpx
import pytest
from pydantic import SecretStr

from fintect.banking.http_client import create_fineract_client
from fintect.config import Settings


@pytest.mark.anyio
async def test_fineract_client_configuration():
    settings = Settings(
        _env_file=None,
        fineract_base_url="https://localhost:8443/fineract-provider/api/v1",
        fineract_username="test-user",
        fineract_password=SecretStr("test-secret"),
        fineract_tenant_id="test-tenant",
        fineract_timeout_seconds=20.0,
        fineract_verify_tls=False,
    )

    expected_auth = base64.b64encode(b"test-user:test-secret").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Basic {expected_auth}"
        assert request.headers["Fineract-Platform-TenantId"] == "test-tenant"

        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    client = create_fineract_client(settings, transport=transport)

    try:
        response = await client.get("test-endpoint")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert str(client.base_url) == (
            "https://localhost:8443/fineract-provider/api/v1/"
        )
        assert client.timeout.read == 20.0
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_client_uses_default_tenant():
    settings = Settings(_env_file=None)
    client = create_fineract_client(settings)

    try:
        assert client.headers["Fineract-Platform-TenantId"] == "default"
    finally:
        await client.aclose()
