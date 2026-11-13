from datetime import datetime
from decimal import Decimal

import httpx
import pytest

from fintect.banking.fineract_adapter import FineractAdapter
from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    AccountDetailsRequest,
    AccountDetailsResponse,
    AccountLookupRequest,
    AccountLookupResponse,
    BankingErrorCode,
    BankingException,
    BankingTransaction,
    CustomerDetails,
    CustomerLookupRequest,
    CustomerSavingsAccount,
    SavingsAccountOverview,
    SavingsAccountOverviewRequest,
    TransactionDetailsRequest,
    TransactionHistoryRequest,
    TransactionHistoryResponse,
)
from fintect.config import Settings
from fintect.domain.enums import AccountStatus, TransactionStatus


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


@pytest.mark.anyio
async def test_fineract_adapter_returns_account_details():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/savingsaccounts/1")

        return httpx.Response(
            200,
            json={
                "id": 1,
                "accountNo": "000000001",
                "clientId": 10,
                "status": {
                    "id": 300,
                    "code": "savingsAccountStatusType.active",
                    "value": "Active",
                },
                "currency": {"code": "USD"},
                "name": "Primary Savings",
                "productName": "Savings Product",
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_account_details(
            AccountDetailsRequest(account_id="1")
        )

        assert isinstance(result, AccountDetailsResponse)
        assert result.account_id == "1"
        assert result.account_number == "000000001"
        assert result.account_name == "Primary Savings"
        assert result.account_status == AccountStatus.ACTIVE
        assert result.currency == "USD"
        assert result.product_name == "Savings Product"
        assert result.client_id == "10"
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("fineract_status", "expected_status"),
    [
        ("Active", AccountStatus.ACTIVE),
        ("Approved", AccountStatus.ACTIVE),
        ("Frozen", AccountStatus.FROZEN),
        ("Closed", AccountStatus.CLOSED),
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_account_status(
    fineract_status: str,
    expected_status: AccountStatus,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 1,
                "accountNo": "000000001",
                "status": {"value": fineract_status},
                "currency": {"code": "USD"},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_account_details(
            AccountDetailsRequest(account_id="1")
        )
        assert result.account_status == expected_status
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_rejects_unknown_account_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 1,
                "accountNo": "000000001",
                "status": {"value": "Pending"},
                "currency": {"code": "USD"},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_details(AccountDetailsRequest(account_id="1"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_OPERATION_FAILED
        assert error.operation == "get_account_details"
        assert error.retryable is False
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_maps_account_details_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"internal": "hidden"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_details(AccountDetailsRequest(account_id="999"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.ACCOUNT_NOT_FOUND
        assert error.operation == "get_account_details"
        assert "hidden" not in error.message
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
            "status": {},
            "currency": {"code": "USD"},
        },
        {
            "id": 1,
            "accountNo": "000000001",
            "status": {"value": "Active"},
            "currency": {},
        },
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_malformed_account_details(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_account_details(AccountDetailsRequest(account_id="1"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_OPERATION_FAILED
        assert error.operation == "get_account_details"
        assert error.retryable is False
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_returns_transaction_history():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/savingsaccounts/1/transactions")
        assert request.url.params["offset"] == "0"
        assert request.url.params["limit"] == "20"

        return httpx.Response(
            200,
            json={
                "totalFilteredRecords": 2,
                "transactions": [
                    {
                        "id": 101,
                        "accountId": 1,
                        "date": [2026, 11, 12],
                        "transactionType": {"value": "Deposit"},
                        "amount": 500.00,
                        "currency": {"code": "INR"},
                        "note": "Salary",
                        "reversed": False,
                    },
                    {
                        "id": 102,
                        "accountId": 1,
                        "date": "2026-11-12",
                        "transactionType": {"value": "Withdrawal"},
                        "amount": 200.00,
                        "currency": {"code": "INR"},
                        "note": "ATM",
                        "reversed": True,
                    },
                ],
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_transaction_history(
            TransactionHistoryRequest(account_id="1")
        )

        assert isinstance(result, TransactionHistoryResponse)
        assert result.account_id == "1"
        assert result.total_count == 2
        assert result.limit == 20
        assert result.offset == 0
        assert len(result.transactions) == 2

        deposit = result.transactions[0]
        assert isinstance(deposit, BankingTransaction)
        assert deposit.transaction_id == "101"
        assert deposit.account_id == "1"
        assert deposit.transaction_type == "deposit"
        assert deposit.amount == Decimal("500.0")
        assert deposit.currency == "INR"
        assert deposit.status == TransactionStatus.COMPLETED
        assert deposit.description == "Salary"
        assert deposit.transaction_date == datetime(2026, 11, 12)

        withdrawal = result.transactions[1]
        assert withdrawal.transaction_id == "102"
        assert withdrawal.transaction_type == "withdrawal"
        assert withdrawal.amount == Decimal("200.0")
        assert withdrawal.status == TransactionStatus.REVERSED
        assert withdrawal.description == "ATM"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_passes_transaction_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["offset"] == "40"
        assert request.url.params["limit"] == "10"

        return httpx.Response(
            200,
            json={
                "totalFilteredRecords": 100,
                "transactions": [],
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_transaction_history(
            TransactionHistoryRequest(account_id="1", limit=10, offset=40)
        )

        assert result.transactions == []
        assert result.total_count == 100
        assert result.limit == 10
        assert result.offset == 40
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_maps_transaction_history_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"message": "Savings account not found"},
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
            await adapter.get_transaction_history(
                TransactionHistoryRequest(account_id="999")
            )

        assert exc_info.value.error.code == BankingErrorCode.ACCOUNT_NOT_FOUND

    finally:
        await client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"transactions": None},
        {"transactions": [{}]},
        {"transactions": [{"id": 1}]},
        {"transactions": [{"id": 1, "date": "invalid-date"}]},
    ],
)
async def test_fineract_adapter_maps_malformed_transaction_history(
    payload: dict,
):
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
            await adapter.get_transaction_history(
                TransactionHistoryRequest(account_id="1")
            )

        assert exc_info.value.error.code == BankingErrorCode.BANKING_OPERATION_FAILED

    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_returns_transaction_details():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/savingsaccounts/1/transactions/101")
        return httpx.Response(
            200,
            json={
                "id": 101,
                "accountId": 1,
                "date": [2026, 11, 12],
                "transactionType": {"value": "Deposit"},
                "amount": 500.00,
                "currency": {"code": "INR"},
                "note": "Salary",
                "reversed": False,
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
        result = await adapter.get_transaction_details(
            TransactionDetailsRequest(
                account_id="1",
                transaction_id="101",
            )
        )

        assert isinstance(result, BankingTransaction)
        assert result.transaction_id == "101"
        assert result.account_id == "1"
        assert result.transaction_type == "deposit"
        assert result.amount == Decimal("500.0")
        assert result.currency == "INR"
        assert result.transaction_date == datetime(2026, 11, 12)
        assert result.status == TransactionStatus.COMPLETED
        assert result.description == "Salary"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_returns_reversed_transaction_details():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 102,
                "accountId": 1,
                "date": "2026-11-12",
                "transactionType": {"value": "Withdrawal"},
                "amount": 200.00,
                "currency": {"code": "INR"},
                "note": "ATM",
                "reversed": True,
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
        result = await adapter.get_transaction_details(
            TransactionDetailsRequest(
                account_id="1",
                transaction_id="102",
            )
        )

        assert result.transaction_id == "102"
        assert result.transaction_type == "withdrawal"
        assert result.status == TransactionStatus.REVERSED
        assert result.description == "ATM"
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("status_code", "expected_code", "retryable"),
    [
        (404, BankingErrorCode.ACCOUNT_NOT_FOUND, False),
        (401, BankingErrorCode.BANKING_AUTHENTICATION_FAILED, False),
        (403, BankingErrorCode.BANKING_AUTHENTICATION_FAILED, False),
        (500, BankingErrorCode.BANKING_SERVICE_UNAVAILABLE, True),
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_transaction_details_http_errors(
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
            await adapter.get_transaction_details(
                TransactionDetailsRequest(
                    account_id="1",
                    transaction_id="101",
                )
            )

        error = exc_info.value.error
        assert error.code == expected_code
        assert error.retryable is retryable
        assert error.operation == "get_transaction_details"
        assert "Do not expose this" not in error.message
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_maps_transaction_details_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request timed out")

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
            await adapter.get_transaction_details(
                TransactionDetailsRequest(
                    account_id="1",
                    transaction_id="101",
                )
            )

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_SERVICE_UNAVAILABLE
        assert error.retryable is True
        assert error.operation == "get_transaction_details"
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": 101},
        {
            "id": 101,
            "accountId": 1,
            "date": [2026, 11, 12],
            "transactionType": {"value": "Deposit"},
            "amount": "invalid",
            "currency": {"code": "INR"},
        },
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_malformed_transaction_details(payload):
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
            await adapter.get_transaction_details(
                TransactionDetailsRequest(
                    account_id="1",
                    transaction_id="101",
                )
            )

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_OPERATION_FAILED
        assert error.operation == "get_transaction_details"
        assert error.retryable is False
    finally:
        await client.aclose()


# M1.4: Savings account overview adapter tests


@pytest.mark.anyio
async def test_fineract_adapter_returns_savings_account_overview():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/savingsaccounts/1")

        return httpx.Response(
            200,
            json={
                "id": 1,
                "accountNo": "000000001",
                "name": "My Savings",
                "status": {"value": "Active"},
                "currency": {"code": "USD"},
                "productName": "Savings",
                "clientId": 10,
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
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_savings_account_overview(
            SavingsAccountOverviewRequest(account_id="1")
        )

        assert isinstance(result, SavingsAccountOverview)
        assert result.account_id == "1"
        assert result.account_number == "000000001"
        assert result.account_name == "My Savings"
        assert result.account_status == AccountStatus.ACTIVE
        assert result.currency == "USD"
        assert result.product_name == "Savings"
        assert result.client_id == "10"
        assert result.account_balance == Decimal("1250.50")
        assert result.available_balance == Decimal("1200.00")
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("status_value", "expected_status"),
    [
        ("Active", AccountStatus.ACTIVE),
        ("Approved", AccountStatus.ACTIVE),
        ("Frozen", AccountStatus.FROZEN),
        ("Closed", AccountStatus.CLOSED),
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_overview_account_status(
    status_value: str,
    expected_status: AccountStatus,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 1,
                "accountNo": "000000001",
                "status": {"value": status_value},
                "currency": {"code": "USD"},
                "summary": {
                    "accountBalance": 100,
                    "availableBalance": 90,
                },
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_savings_account_overview(
            SavingsAccountOverviewRequest(account_id="1")
        )

        assert result.account_status == expected_status
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_overview_maps_404_to_account_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Provider details"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_savings_account_overview(
                SavingsAccountOverviewRequest(account_id="999")
            )

        error = exc_info.value.error
        assert error.code == BankingErrorCode.ACCOUNT_NOT_FOUND
        assert error.operation == "get_savings_account_overview"
        assert error.retryable is False
        assert "Provider details" not in error.message
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_overview_maps_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request timed out")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_savings_account_overview(
                SavingsAccountOverviewRequest(account_id="1")
            )

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_SERVICE_UNAVAILABLE
        assert error.retryable is True
        assert error.operation == "get_savings_account_overview"
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
            "status": {"value": "Unknown"},
            "currency": {"code": "USD"},
            "summary": {
                "accountBalance": 100,
                "availableBalance": 90,
            },
        },
        {
            "id": 1,
            "accountNo": "000000001",
            "status": {"value": "Active"},
            "currency": {"code": "USD"},
            "summary": {
                "accountBalance": "invalid",
                "availableBalance": 90,
            },
        },
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_overview_rejects_invalid_response(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_savings_account_overview(
                SavingsAccountOverviewRequest(account_id="1")
            )

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_OPERATION_FAILED
        assert error.operation == "get_savings_account_overview"
        assert error.retryable is False
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_returns_customer_details():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/clients/1")

        return httpx.Response(
            200,
            json={
                "id": 1,
                "displayName": "Rahul Sharma",
                "status": {"value": "Active"},
                "officeName": "Head Office",
                "active": True,
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
        result = await adapter.get_customer_details(
            CustomerLookupRequest(client_id="1")
        )

        assert isinstance(result, CustomerDetails)
        assert result.client_id == "1"
        assert result.client_name == "Rahul Sharma"
        assert result.client_status == "Active"
        assert result.office_name == "Head Office"
        assert result.active is True
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_maps_customer_404():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/clients/999")
        return httpx.Response(404, json={"error": "Internal provider details"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_customer_details(CustomerLookupRequest(client_id="999"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.ACCOUNT_NOT_FOUND
        assert error.operation == "get_customer_details"
        assert error.retryable is False
        assert "Internal provider details" not in error.message
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": 1},
        {
            "id": 1,
            "displayName": "Rahul Sharma",
            "status": {"value": "Active"},
            "officeName": "Head Office",
        },
        {
            "id": 1,
            "displayName": "Rahul Sharma",
            "status": {"value": "Active"},
            "officeName": "Head Office",
            "active": "invalid",
        },
    ],
)
@pytest.mark.anyio
async def test_fineract_adapter_maps_malformed_customer_response(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException) as exc_info:
            await adapter.get_customer_details(CustomerLookupRequest(client_id="1"))

        error = exc_info.value.error
        assert error.code == BankingErrorCode.BANKING_OPERATION_FAILED
        assert error.operation == "get_customer_details"
        assert error.retryable is False
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_returns_customer_savings_accounts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/clients/1/accounts")
        assert request.url.params["fields"] == "savingsAccounts"

        return httpx.Response(
            200,
            json={
                "savingsAccounts": [
                    {
                        "id": 101,
                        "accountNo": "000000101",
                        "productName": "Passbook Savings",
                        "status": {"value": "Active"},
                    },
                    {
                        "id": 102,
                        "accountNo": "000000102",
                        "productName": "Regular Savings",
                        "status": {"value": "Closed"},
                    },
                ]
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_customer_accounts(
            AccountLookupRequest(client_id="1")
        )

        assert isinstance(result, AccountLookupResponse)
        assert result.client_id == "1"
        assert len(result.savings_accounts) == 2

        first_account = result.savings_accounts[0]
        assert isinstance(first_account, CustomerSavingsAccount)
        assert first_account.account_id == "101"
        assert first_account.account_number == "000000101"
        assert first_account.product_name == "Passbook Savings"
        assert first_account.account_status == "Active"

        second_account = result.savings_accounts[1]
        assert second_account.account_id == "102"
        assert second_account.account_status == "Closed"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_returns_empty_customer_savings_accounts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/clients/1/accounts")
        return httpx.Response(200, json={"savingsAccounts": []})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        result = await adapter.get_customer_accounts(
            AccountLookupRequest(client_id="1")
        )

        assert isinstance(result, AccountLookupResponse)
        assert result.client_id == "1"
        assert result.savings_accounts == []
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_rejects_malformed_customer_savings_accounts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "savingsAccounts": [
                    {
                        "id": 101,
                        "accountNo": "000000101",
                        # Missing productName and status
                    }
                ]
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
        with pytest.raises(BankingException):
            await adapter.get_customer_accounts(AccountLookupRequest(client_id="1"))
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_rejects_missing_savings_accounts_field():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["fields"] == "savingsAccounts"

        return httpx.Response(
            200,
            json={},
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://fineract.test/api/v1/",
    )
    adapter = FineractAdapter(settings=Settings(_env_file=None), client=client)

    try:
        with pytest.raises(BankingException):
            await adapter.get_customer_accounts(AccountLookupRequest(client_id="1"))
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fineract_adapter_customer_accounts_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"message": "Client not found"},
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
            await adapter.get_customer_accounts(AccountLookupRequest(client_id="999"))

        assert exc_info.value.error.code == BankingErrorCode.ACCOUNT_NOT_FOUND
    finally:
        await client.aclose()
