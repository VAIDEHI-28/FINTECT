from decimal import Decimal

import httpx
import pytest

from fintect.banking.fineract_adapter import FineractAdapter
from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    BankingErrorCode,
    BankingException,
)
from fintect.config import Settings


@pytest.mark.anyio
async def test_fineract_adapter_returns_account_balance():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/savingsaccounts/1")

        return httpx.Response(
            200,
            json={
                "id": 1,
                "accountNo": "000000001",
                "currency": {"code": "USD"},
                "summary": {
                    "accountBalance": 1250.50,
                    "availableBalance": 1200.00,
                },
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )

    adapter = FineractAdapter(
        settings=Settings(_env_file=None),
        client=client,
    )

    try:
        result = await adapter.get_account_balance(
            AccountBalanceRequest(account_id="1")
        )

        assert isinstance(result, AccountBalanceResponse)
        assert result.account_id == "1"
        assert result.account_number == "000000001"
        assert result.currency == "USD"
        assert result.account_balance == Decimal("1250.50")
        assert result.available_balance == Decimal("1200.00")
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_maps_404_to_account_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Internal provider details"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_balance(AccountBalanceRequest(account_id="999"))

        error = exc_info.value.error

        assert error.code == BankingErrorCode.ACCOUNT_NOT_FOUND
        assert error.message == "Bank account was not found."
        assert error.operation == "get_account_balance"
        assert error.retryable is False
        assert "Internal provider details" not in error.message
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("status_code", "expected_code", "retryable"),
    [
        (400, BankingErrorCode.INVALID_REQUEST, False),
        (401, BankingErrorCode.BANKING_AUTHENTICATION_FAILED, False),
        (403, BankingErrorCode.BANKING_AUTHENTICATION_FAILED, False),
        (404, BankingErrorCode.ACCOUNT_NOT_FOUND, False),
        (429, BankingErrorCode.BANKING_SERVICE_UNAVAILABLE, True),
        (500, BankingErrorCode.BANKING_SERVICE_UNAVAILABLE, True),
        (502, BankingErrorCode.BANKING_SERVICE_UNAVAILABLE, True),
        (503, BankingErrorCode.BANKING_SERVICE_UNAVAILABLE, True),
        (422, BankingErrorCode.BANKING_OPERATION_FAILED, False),
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_http_errors(
    status_code: int,
    expected_code: BankingErrorCode,
    retryable: bool,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"internal_details": "Do not expose this"},
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(
        settings=Settings(_env_file=None),
        client=client,
    )

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_balance(AccountBalanceRequest(account_id="1"))

        error = exc_info.value.error
        assert error.code == expected_code
        assert error.retryable is retryable
        assert error.operation == "get_account_balance"
        assert "Do not expose this" not in error.message
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (
            httpx.ReadTimeout("request timed out"),
            "Banking service request timed out.",
        ),
        (
            httpx.ConnectError("connection failed"),
            "Unable to connect to banking service.",
        ),
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_network_errors(
    exception: Exception,
    expected_message: str,
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(
        settings=Settings(_env_file=None),
        client=client,
    )

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_balance(AccountBalanceRequest(account_id="1"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_SERVICE_UNAVAILABLE
        assert error.message == expected_message
        assert error.retryable is True
        assert error.operation == "get_account_balance"
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": 1},
        {
            "id": 1,
            "accountNo": "000000001",
            "currency": {"code": "USD"},
            "summary": {},
        },
        {
            "id": 1,
            "accountNo": "000000001",
            "currency": {"code": "USD"},
            "summary": {
                "accountBalance": "invalid",
                "availableBalance": "100",
            },
        },
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_malformed_responses(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(
        settings=Settings(_env_file=None),
        client=client,
    )

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_balance(AccountBalanceRequest(account_id="1"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_OPERATION_FAILED
        assert error.message == "Banking service returned an invalid response."
        assert error.retryable is False
    finally:
        await client.aclose()
