from decimal import Decimal

import pytest

from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
)


class FakeBankingAdapter:
    async def get_account_balance(
        self,
        request: AccountBalanceRequest,
    ) -> AccountBalanceResponse:
        return AccountBalanceResponse(
            account_id=request.account_id,
            account_number="000000001",
            currency="USD",
            account_balance=Decimal("100.00"),
            available_balance=Decimal("100.00"),
        )


@pytest.mark.anyio
async def test_fake_adapter_returns_balance():
    adapter = FakeBankingAdapter()

    response = await adapter.get_account_balance(AccountBalanceRequest(account_id="1"))

    assert response.account_id == "1"
    assert response.account_balance == Decimal("100.00")
