from typing import Protocol

from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    AccountDetailsRequest,
    AccountDetailsResponse,
    BankingTransaction,
    CustomerDetails,
    CustomerLookupRequest,
    SavingsAccountOverview,
    SavingsAccountOverviewRequest,
    TransactionDetailsRequest,
    TransactionHistoryRequest,
    TransactionHistoryResponse,
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

    async def get_transaction_history(
        self,
        request: TransactionHistoryRequest,
    ) -> TransactionHistoryResponse:
        """Retrieve savings account transaction history."""
        ...

    async def get_transaction_details(
        self,
        request: TransactionDetailsRequest,
    ) -> BankingTransaction:
        """Retrieve details of a specific savings account transaction."""
        ...

    async def get_savings_account_overview(
        self,
        request: SavingsAccountOverviewRequest,
    ) -> SavingsAccountOverview:
        """Retrieve savings account metadata and balances."""
        ...

    async def get_customer_details(
        self,
        request: CustomerLookupRequest,
    ) -> CustomerDetails:
        """Retrieve customer details."""
        ...
