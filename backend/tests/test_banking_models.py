from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    AccountDetailsRequest,
    AccountDetailsResponse,
    BankingError,
    BankingErrorCode,
    BankingTransaction,
    SavingsAccountOverview,
    SavingsAccountOverviewRequest,
    TransactionDetailsRequest,
    TransactionHistoryRequest,
    TransactionHistoryResponse,
)
from fintect.domain.enums import AccountStatus, TransactionStatus


def test_account_balance_request_valid():
    request = AccountBalanceRequest(account_id="1")
    assert request.account_id == "1"


@pytest.mark.parametrize("account_id", ["", "   "])
def test_account_balance_request_rejects_blank_id(account_id):
    with pytest.raises(ValidationError):
        AccountBalanceRequest(account_id=account_id)


def test_account_balance_response_valid():
    response = AccountBalanceResponse(
        account_id="1",
        account_number="000000001",
        currency="USD",
        account_balance=Decimal("100.50"),
        available_balance=Decimal("90.50"),
    )

    assert response.account_balance == Decimal("100.50")
    assert response.available_balance == Decimal("90.50")


@pytest.mark.parametrize("value", [100.50, 100, "100.50"])
def test_account_balance_response_rejects_non_decimal(value):
    with pytest.raises(ValidationError):
        AccountBalanceResponse(
            account_id="1",
            account_number="000000001",
            currency="USD",
            account_balance=value,
            available_balance=Decimal("90.50"),
        )


def test_banking_error_defaults_to_non_retryable():
    error = BankingError(
        code=BankingErrorCode.ACCOUNT_NOT_FOUND,
        message="Account not found",
        operation="get_account_balance",
    )

    assert error.retryable is False


def test_account_details_request_valid() -> None:
    request = AccountDetailsRequest(account_id="1")

    assert request.account_id == "1"


@pytest.mark.parametrize("account_id", ["", "   "])
def test_account_details_request_rejects_blank_id(
    account_id: str,
) -> None:
    with pytest.raises(ValidationError):
        AccountDetailsRequest(account_id=account_id)


def test_account_details_response_valid() -> None:
    response = AccountDetailsResponse(
        account_id="1",
        account_number="000000001",
        account_name="Savings Account",
        account_status=AccountStatus.ACTIVE,
        currency="USD",
        product_name="Savings",
        client_id="1",
    )

    assert response.account_id == "1"
    assert response.account_number == "000000001"
    assert response.account_status == AccountStatus.ACTIVE
    assert response.currency == "USD"


def test_banking_transaction_valid():
    transaction = BankingTransaction(
        transaction_id="101",
        account_id="1",
        transaction_type="deposit",
        amount=Decimal("500.00"),
        currency="INR",
        transaction_date=datetime(2026, 11, 12, tzinfo=timezone.utc),
        status=TransactionStatus.COMPLETED,
        description="Salary",
    )

    assert transaction.transaction_id == "101"
    assert transaction.amount == Decimal("500.00")
    assert transaction.status == TransactionStatus.COMPLETED


def test_transaction_history_request_defaults():
    request = TransactionHistoryRequest(account_id="1")

    assert request.limit == 20
    assert request.offset == 0


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_transaction_history_request_rejects_invalid_limit(limit):
    with pytest.raises(ValidationError):
        TransactionHistoryRequest(account_id="1", limit=limit)


@pytest.mark.parametrize("offset", [-1, -10])
def test_transaction_history_request_rejects_negative_offset(offset):
    with pytest.raises(ValidationError):
        TransactionHistoryRequest(account_id="1", offset=offset)


def test_transaction_history_response_valid():
    transaction = BankingTransaction(
        transaction_id="101",
        account_id="1",
        transaction_type="deposit",
        amount=Decimal("500.00"),
        currency="INR",
        transaction_date=datetime(2026, 11, 12, tzinfo=timezone.utc),
        status=TransactionStatus.COMPLETED,
    )

    response = TransactionHistoryResponse(
        account_id="1",
        transactions=[transaction],
        total_count=100,
        limit=20,
        offset=0,
    )

    assert len(response.transactions) == 1
    assert response.total_count == 100


# M1.3: Transaction details request tests


def test_transaction_details_request_valid():
    request = TransactionDetailsRequest(
        account_id="1",
        transaction_id="101",
    )

    assert request.account_id == "1"
    assert request.transaction_id == "101"


@pytest.mark.parametrize("account_id", ["", "   "])
def test_transaction_details_request_rejects_blank_account_id(
    account_id: str,
):
    with pytest.raises(ValidationError):
        TransactionDetailsRequest(
            account_id=account_id,
            transaction_id="101",
        )


@pytest.mark.parametrize("transaction_id", ["", "   "])
def test_transaction_details_request_rejects_blank_transaction_id(
    transaction_id: str,
):
    with pytest.raises(ValidationError):
        TransactionDetailsRequest(
            account_id="1",
            transaction_id=transaction_id,
        )


# M1.4: Savings account overview model tests


def test_savings_account_overview_request_valid():
    request = SavingsAccountOverviewRequest(account_id="1")

    assert request.account_id == "1"


@pytest.mark.parametrize("account_id", ["", "   "])
def test_savings_account_overview_request_rejects_blank_id(account_id):
    with pytest.raises(ValidationError):
        SavingsAccountOverviewRequest(account_id=account_id)


def test_savings_account_overview_valid():
    overview = SavingsAccountOverview(
        account_id="1",
        account_number="000000001",
        account_name="Savings Account",
        account_status=AccountStatus.ACTIVE,
        currency="USD",
        product_name="Savings",
        client_id="1",
        account_balance=Decimal("1000.50"),
        available_balance=Decimal("900.50"),
    )

    assert overview.account_id == "1"
    assert overview.account_status == AccountStatus.ACTIVE
    assert overview.account_balance == Decimal("1000.50")
    assert overview.available_balance == Decimal("900.50")


@pytest.mark.parametrize("value", [100.50, 100, "100.50"])
def test_savings_account_overview_rejects_non_decimal_balance(value):
    with pytest.raises(ValidationError):
        SavingsAccountOverview(
            account_id="1",
            account_number="000000001",
            account_status=AccountStatus.ACTIVE,
            currency="USD",
            account_balance=value,
            available_balance=Decimal("900.50"),
        )


@pytest.mark.parametrize("currency", ["US", "USDD", ""])
def test_savings_account_overview_rejects_invalid_currency(currency):
    with pytest.raises(ValidationError):
        SavingsAccountOverview(
            account_id="1",
            account_number="000000001",
            account_status=AccountStatus.ACTIVE,
            currency=currency,
            account_balance=Decimal("1000.00"),
            available_balance=Decimal("900.00"),
        )
