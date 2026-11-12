from typing import Protocol

from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    AccountDetailsRequest,
    AccountDetailsResponse,
)


class BankingInterface(Protocol):
    """Canonical interface for banking operations."""

    async def get_account_balance(
        self,
        request: AccountBalanceRequest,
    ) -> AccountBalanceResponse:
        """Retrieve an account balance."""
        ...

    async def get_account_details(
        self,
        request: AccountDetailsRequest,
    ) -> AccountDetailsResponse:
        """Retrieve account details."""
        ...
