import httpx

from fintect.config import Settings


def create_fineract_client(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Create a configured asynchronous HTTP client for Fineract."""
    return httpx.AsyncClient(
        base_url=settings.fineract_base_url.rstrip("/") + "/",
        auth=(
            settings.fineract_username,
            settings.fineract_password.get_secret_value(),
        ),
        headers={
            "Fineract-Platform-TenantId": settings.fineract_tenant_id,
        },
        timeout=settings.fineract_timeout_seconds,
        verify=settings.fineract_verify_tls,
        transport=transport,
    )
