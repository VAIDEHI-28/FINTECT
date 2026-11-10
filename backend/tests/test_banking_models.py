from decimal import Decimal

import pytest
from pydantic import ValidationError

from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    BankingError,
    BankingErrorCode,
)


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
