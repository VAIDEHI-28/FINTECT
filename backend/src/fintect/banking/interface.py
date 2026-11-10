from typing import Protocol

from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
)


class BankingInterface(Protocol):
    async def get_account_balance(
        self,
        request: AccountBalanceRequest,
    ) -> AccountBalanceResponse:
        """Retrieve an account's balance."""
        ...
