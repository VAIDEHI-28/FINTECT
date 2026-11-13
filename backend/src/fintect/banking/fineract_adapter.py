from datetime import datetime
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import ValidationError

from fintect.banking.http_client import create_fineract_client
from fintect.banking.interface import BankingInterface
from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    AccountDetailsRequest,
    AccountDetailsResponse,
    AccountLookupRequest,
    AccountLookupResponse,
    BankingError,
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


class FineractAdapter(BankingInterface):
    """Banking adapter backed by Apache Fineract."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or create_fineract_client(settings)

    @staticmethod
    def _raise_for_banking_error(
        response: httpx.Response,
        operation: str,
    ) -> None:
        """Translate Fineract HTTP errors into canonical banking errors."""
        status_code = response.status_code

        if status_code < 400:
            return

        if status_code == 404:
            code = BankingErrorCode.ACCOUNT_NOT_FOUND
            message = "Bank account was not found."
            retryable = False
        elif status_code == 400:
            code = BankingErrorCode.INVALID_REQUEST
            message = "Banking request is invalid."
            retryable = False
        elif status_code in (401, 403):
            code = BankingErrorCode.BANKING_AUTHENTICATION_FAILED
            message = "Banking service authentication failed."
            retryable = False
        elif status_code == 429 or status_code >= 500:
            code = BankingErrorCode.BANKING_SERVICE_UNAVAILABLE
            message = "Banking service is temporarily unavailable."
            retryable = True
        else:
            code = BankingErrorCode.BANKING_OPERATION_FAILED
            message = "Banking operation failed."
            retryable = False

        raise BankingException(
            BankingError(
                code=code,
                message=message,
                operation=operation,
                retryable=retryable,
            )
        )

    @staticmethod
    def _raise_for_request_error(
        exc: httpx.RequestError,
        operation: str,
    ) -> None:
        """Translate network errors into canonical banking errors."""
        if isinstance(exc, httpx.TimeoutException):
            message = "Banking service request timed out."
        else:
            message = "Unable to connect to banking service."

        raise BankingException(
            BankingError(
                code=BankingErrorCode.BANKING_SERVICE_UNAVAILABLE,
                message=message,
                operation=operation,
                retryable=True,
            )
        ) from exc

    @staticmethod
    def _raise_for_invalid_response(operation: str) -> None:
        """Raise a safe canonical error for malformed Fineract responses."""
        raise BankingException(
            BankingError(
                code=BankingErrorCode.BANKING_OPERATION_FAILED,
                message="Banking service returned an invalid response.",
                operation=operation,
                retryable=False,
            )
        )

    async def get_account_balance(
        self,
        request: AccountBalanceRequest,
    ) -> AccountBalanceResponse:
        """Retrieve an account balance from Fineract."""
        operation = "get_account_balance"

        try:
            response = await self._client.get(f"savingsaccounts/{request.account_id}")
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            data = response.json()
            summary = data["summary"]

            return AccountBalanceResponse(
                account_id=str(data["id"]),
                account_number=str(data["accountNo"]),
                currency=data["currency"]["code"],
                account_balance=Decimal(str(summary["accountBalance"])),
                available_balance=Decimal(str(summary["availableBalance"])),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc

    async def get_account_details(
        self,
        request: AccountDetailsRequest,
    ) -> AccountDetailsResponse:
        """Retrieve account details from Fineract."""
        operation = "get_account_details"

        try:
            response = await self._client.get(f"savingsaccounts/{request.account_id}")
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            data = response.json()
            status_value = data["status"]["value"].lower()

            status_mapping = {
                "active": AccountStatus.ACTIVE,
                "approved": AccountStatus.ACTIVE,
                "frozen": AccountStatus.FROZEN,
                "closed": AccountStatus.CLOSED,
            }

            account_status = status_mapping.get(status_value)
            if account_status is None:
                self._raise_for_invalid_response(operation)

            return AccountDetailsResponse(
                account_id=str(data["id"]),
                account_number=str(data["accountNo"]),
                account_name=data.get("name"),
                account_status=account_status,
                currency=data["currency"]["code"],
                product_name=data.get("productName"),
                client_id=(
                    str(data["clientId"]) if data.get("clientId") is not None else None
                ),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc

    async def get_transaction_history(
        self,
        request: TransactionHistoryRequest,
    ) -> TransactionHistoryResponse:
        """Retrieve paginated savings account transactions from Fineract."""
        operation = "get_transaction_history"

        try:
            response = await self._client.get(
                f"savingsaccounts/{request.account_id}/transactions",
                params={
                    "offset": request.offset,
                    "limit": request.limit,
                },
            )
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            data = response.json()
            records = data["transactions"]

            transactions = []
            for item in records:
                raw_date = item["date"]

                if isinstance(raw_date, list):
                    transaction_date = datetime(*raw_date)
                else:
                    transaction_date = datetime.fromisoformat(
                        str(raw_date).replace("Z", "+00:00")
                    )

                status = (
                    TransactionStatus.REVERSED
                    if item.get("reversed", False)
                    else TransactionStatus.COMPLETED
                )

                transactions.append(
                    BankingTransaction(
                        transaction_id=str(item["id"]),
                        account_id=str(item["accountId"]),
                        transaction_type=item["transactionType"]["value"].lower(),
                        amount=Decimal(str(item["amount"])),
                        currency=item["currency"]["code"],
                        transaction_date=transaction_date,
                        status=status,
                        description=item.get("note"),
                    )
                )

            return TransactionHistoryResponse(
                account_id=request.account_id,
                transactions=transactions,
                total_count=data.get("totalFilteredRecords"),
                limit=request.limit,
                offset=request.offset,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc

    async def get_transaction_details(
        self,
        request: TransactionDetailsRequest,
    ) -> BankingTransaction:
        """Retrieve a specific savings account transaction from Fineract."""
        operation = "get_transaction_details"

        try:
            response = await self._client.get(
                f"savingsaccounts/{request.account_id}/transactions/"
                f"{request.transaction_id}"
            )
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            item = response.json()
            raw_date = item["date"]

            if isinstance(raw_date, list):
                transaction_date = datetime(*raw_date)
            else:
                transaction_date = datetime.fromisoformat(
                    str(raw_date).replace("Z", "+00:00")
                )

            status = (
                TransactionStatus.REVERSED
                if item.get("reversed", False)
                else TransactionStatus.COMPLETED
            )

            return BankingTransaction(
                transaction_id=str(item["id"]),
                account_id=str(item["accountId"]),
                transaction_type=item["transactionType"]["value"].lower(),
                amount=Decimal(str(item["amount"])),
                currency=item["currency"]["code"],
                transaction_date=transaction_date,
                status=status,
                description=item.get("note"),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc

    async def get_savings_account_overview(
        self,
        request: SavingsAccountOverviewRequest,
    ) -> SavingsAccountOverview:
        """Retrieve savings account metadata and balances from Fineract."""
        operation = "get_savings_account_overview"

        try:
            response = await self._client.get(f"savingsaccounts/{request.account_id}")
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            data = response.json()
            summary = data["summary"]
            status_value = data["status"]["value"].lower()

            status_mapping = {
                "active": AccountStatus.ACTIVE,
                "approved": AccountStatus.ACTIVE,
                "frozen": AccountStatus.FROZEN,
                "closed": AccountStatus.CLOSED,
            }

            account_status = status_mapping.get(status_value)
            if account_status is None:
                self._raise_for_invalid_response(operation)

            return SavingsAccountOverview(
                account_id=str(data["id"]),
                account_number=str(data["accountNo"]),
                account_name=data.get("name"),
                account_status=account_status,
                currency=data["currency"]["code"],
                product_name=data.get("productName"),
                client_id=(
                    str(data["clientId"]) if data.get("clientId") is not None else None
                ),
                account_balance=Decimal(str(summary["accountBalance"])),
                available_balance=Decimal(str(summary["availableBalance"])),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc

    async def get_customer_details(
        self,
        request: CustomerLookupRequest,
    ) -> CustomerDetails:
        """Retrieve customer details from Fineract."""
        operation = "get_customer_details"

        try:
            response = await self._client.get(f"clients/{request.client_id}")
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            data = response.json()

            if not isinstance(data, dict):
                self._raise_for_invalid_response(operation)

            return CustomerDetails(
                client_id=str(data["id"]),
                client_name=data["displayName"],
                client_status=data["status"]["value"],
                office_name=data["officeName"],
                active=data["active"],
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc

    async def get_customer_accounts(
        self,
        request: AccountLookupRequest,
    ) -> AccountLookupResponse:
        """Retrieve a customer's savings accounts from Fineract."""
        operation = "get_customer_accounts"

        try:
            response = await self._client.get(
                f"clients/{request.client_id}/accounts",
                params={"fields": "savingsAccounts"},
            )
        except httpx.RequestError as exc:
            self._raise_for_request_error(exc, operation)

        self._raise_for_banking_error(response, operation)

        try:
            data = response.json()

            savings_accounts = [
                CustomerSavingsAccount(
                    account_id=str(account["id"]),
                    account_number=account["accountNo"],
                    product_name=account["productName"],
                    account_status=account["status"]["value"],
                )
                for account in data["savingsAccounts"]
            ]

            return AccountLookupResponse(
                client_id=request.client_id,
                savings_accounts=savings_accounts,
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            self._raise_for_invalid_response(operation)
            raise AssertionError("Unreachable") from exc
